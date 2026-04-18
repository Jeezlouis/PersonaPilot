"""
worker.py — Background worker for processing pending jobs.
Decouples scraping from AI processing (classification, scoring).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models import Job, PendingJob
from backend.config import settings as app_settings
from backend.modules.scraper.normalizer import normalize
from backend.modules.deduplicator.dedup import filter_new_jobs, already_applied_to_company_role
from backend.modules.ai_engine.classifier import classify_job
from backend.modules.scorer.scorer import score_job
from backend.modules.notifier.telegram import notify_new_jobs, notify_error

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
MAX_ATTEMPTS = 3


async def process_pending_jobs():
    """
    Main loop for the processing worker.
    Polls 'pending_jobs' for new entries, processes them through the pipeline,
    and moves them to 'jobs' table if they pass all filters.
    """
    processed_total = 0
    while True:
        async with AsyncSessionLocal() as db:
            # Fetch pending jobs in batches
            result = await db.execute(
                select(PendingJob)
                .where(PendingJob.status == "pending")
                .limit(BATCH_SIZE)
            )
            batch = result.scalars().all()

            if not batch:
                if processed_total > 0:
                    logger.info(f"[Worker] All pending jobs processed. Total: {processed_total}")
                return

            logger.info(f"[Worker] Processing batch of {len(batch)} jobs (Total processed: {processed_total})...")

            for pending in batch:
                pending_id = pending.id  # Cache ID before any risky DB operations
                try:
                    # Mark as processing
                    pending.status = "processing"
                    await db.commit()

                    # 1. Normalize
                    raw_item = pending.raw_data
                    normalized = normalize(
                        source=pending.source,
                        raw=raw_item,
                        title=raw_item.get("title") or "Unknown Title",
                        company=raw_item.get("company"),
                        url=raw_item.get("url", ""),
                        location=raw_item.get("location"),
                        description=raw_item.get("description"),
                        posted_at=raw_item.get("posted_at"),
                        source_id=raw_item.get("source_id"),
                        tags=raw_item.get("tags")
                    )

                    # Hard Validation: URL check (NOT NULL in DB)
                    if not normalized.get("url"):
                        logger.warning(f"[Worker] Skipping pending job {pending_id}: Missing URL.")
                        pending.status = "done" # Move out of queue
                        await db.commit()
                        processed_total += 1
                        continue

                    # 2. Deduplication & Salary Filters
                    # Phase 2E: Salary Filter
                    sal_min_pref = app_settings.salary_minimum
                    if sal_min_pref > 0 and normalized.get("salary_max"):
                        if normalized["salary_max"] < sal_min_pref:
                            logger.info(f"[Worker] Filtered by salary: {normalized['title']} (${normalized['salary_max']} < ${sal_min_pref})")
                            pending.status = "done"
                            await db.commit()
                            processed_total += 1
                            continue

                    # Phase 1B: Already applied check
                    if await already_applied_to_company_role(db, normalized["company"], normalized["title"]):
                        pending.status = "done"
                        await db.commit()
                        processed_total += 1
                        continue

                    # Layer 1 & 2: Hash and URL check via utility
                    new_jobs_list = await filter_new_jobs(db, [normalized])
                    if not new_jobs_list:
                        pending.status = "done"
                        await db.commit()
                        processed_total += 1
                        continue

                    job_data = new_jobs_list[0]

                    # 3. AI Classify
                    classification = await classify_job(job_data, db)
                    category = classification["category"]
                    
                    if category == "not_software":
                        logger.info(f"[Worker] Discarding non-software job: {job_data['title']} at {job_data['company']}")
                        pending.status = "done"
                        await db.commit()
                        processed_total += 1
                        continue

                    job_data["role_category"] = category
                    job_data["employment_type"] = classification.get("employment_type", job_data.get("employment_type", "full-time"))

                    # 4. Score
                    score = await score_job(
                        job_data, db,
                        pref_min=app_settings.salary_min,
                        pref_max=app_settings.salary_max,
                    )
                    job_data["match_score"] = score

                    # Phase 7: Extract Email
                    from backend.modules.mailer.email_extractor import extract_email_info
                    contact_email, contact_confidence = extract_email_info(
                        job_description=job_data.get("description") or "",
                        job_url=job_data.get("url") or "",
                        company_name=job_data.get("company") or ""
                    )
                    job_data["contact_email"] = contact_email
                    job_data["contact_confidence"] = contact_confidence

                    # 5. Auto-skip low-score jobs
                    if score < app_settings.min_match_score:
                        job_data["status"] = "skipped"
                    else:
                        job_data["status"] = "new"

                    # 6. Save to Job table
                    new_job = Job(**{
                        k: v for k, v in job_data.items()
                        if k in Job.__table__.columns.keys()
                    })
                    db.add(new_job)
                    
                    # Update pending status
                    pending.status = "done"
                    await db.commit()
                    processed_total += 1
                    
                    # Routing logic
                    if score >= 70:
                        from backend.api.jobs import draft_application
                        from backend.modules.mailer.email_drafter import generate_email_draft
                        from backend.modules.ai_engine.resume_selector import select_best_resume
                        from backend.models import EmailOutreach
                        from backend.modules.notifier.telegram import notify_email_approval
                        
                        if contact_confidence == "direct":
                            # Queue for email flow
                            new_job.status = "shortlisted"
                            resume_selection = await select_best_resume(job_data, db)
                            if resume_selection:
                                resume = resume_selection["resume"]
                                draft_res = await generate_email_draft(job_data, resume, db)
                                
                                email_out = EmailOutreach(
                                    job_id=new_job.id,
                                    recipient_email=contact_email,
                                    subject=draft_res['subject'],
                                    body=draft_res['body'],
                                    body_preview=draft_res['body'][:100],
                                    resume_used=draft_res['recommended_resume_path']
                                )
                                db.add(email_out)
                                await db.commit()
                                
                                await notify_email_approval(
                                    job_id=new_job.id,
                                    title=new_job.title,
                                    company=new_job.company,
                                    to=contact_email,
                                    subject=draft_res['subject'],
                                    body_preview=draft_res['body'][:200],
                                    resume_name=resume.name
                                )
                                
                        elif contact_confidence == "none":
                            # Standard playwright flow
                            await notify_new_jobs([job_data])
                            # Or we can trigger autofill_job directly or rely on the user
                        elif contact_confidence == "inferred":
                            # Let user decide
                            await notify_new_jobs([job_data])
                    # Moved notification logic inside routing logic above

                except Exception as e:
                    await db.rollback() # CRITICAL: Reset session state after failure
                    logger.error(f"[Worker] Failed to process pending job {pending_id}: {e}")
                    
                    # Re-fetch or re-evaluate status update after rollback
                    try:
                        # We need a fresh query because the session rolled back
                        res = await db.execute(select(PendingJob).where(PendingJob.id == pending_id))
                        to_update = res.scalar_one_or_none()
                        if to_update:
                            to_update.attempts += 1
                            to_update.last_error = str(e)
                            
                            if to_update.attempts >= MAX_ATTEMPTS:
                                to_update.status = "failed"
                                await notify_error("worker_failure", f"Job {pending_id} failed after {MAX_ATTEMPTS} attempts: {e}")
                            else:
                                to_update.status = "pending"  # Retry later
                            
                            await db.commit()
                    except Exception as rb_e:
                        logger.error(f"[Worker] Double-fault during rollback recovery for {pending_id}: {rb_e}")
                    
                    processed_total += 1

        logger.info(f"[Worker] Batch processing complete. Total processed so far: {processed_total}")
