"""
scheduler.py — APScheduler-based task scheduler.
Runs scraping, scoring, notifications, and follow-up checks.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, func, update

from backend.database import AsyncSessionLocal
from backend.models import Job, Application, SchedulerRun
from backend.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


# ─── Task: Full Scrape Pipeline ───────────────────────────────────────────────
async def run_scrape_and_score():
    """Main pipeline: scrape → dedup → score → notify."""
    task_name = "scrape_and_score"
    logger.info(f"[Scheduler] Starting {task_name}")

    async with AsyncSessionLocal() as db:
        # Log run start
        run = SchedulerRun(task_name=task_name, status="running")
        db.add(run)
        await db.flush()
        run_id = run.id

        try:
            from backend.modules.scraper import ALL_SCRAPERS
            from backend.modules.deduplicator.dedup import filter_new_jobs
            from backend.modules.scorer.scorer import score_job
            from backend.modules.ai_engine.classifier import classify_job
            from backend.modules.notifier.telegram import notify_new_jobs
            from backend.models import Job as JobModel

            keywords = settings.search_keywords_list
            all_jobs = []

            for ScraperClass in ALL_SCRAPERS:
                scraper = ScraperClass(keywords=keywords, prefer_remote=True)
                jobs = await scraper.run()
                all_jobs.extend(jobs)
                logger.info(f"Scraper {scraper.source_name}: {len(jobs)} jobs")

            logger.info(f"Total raw jobs: {len(all_jobs)}")

            # Deduplication
            raw_new_jobs = await filter_new_jobs(db, all_jobs)
            
            # Filter older than 1 month
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            new_jobs = []
            for j in raw_new_jobs:
                dt = j.get("posted_at")
                if dt:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                new_jobs.append(j)
                
            logger.info(f"New jobs after dedup and aging: {len(new_jobs)}")

            # Score + classify + save
            high_match_jobs = []
            jobs_added = 0

            for job_data in new_jobs:
                try:
                    # AI classify (updates role_category)
                    classification = await classify_job(job_data)
                    job_data["role_category"] = classification["category"]
                    job_data["employment_type"] = classification.get("employment_type", job_data.get("employment_type", "full-time"))

                    # Score
                    score = await score_job(
                        job_data, db,
                        pref_min=settings.salary_min,
                        pref_max=settings.salary_max,
                    )
                    job_data["match_score"] = score

                    # Auto-skip low-score jobs
                    if score < settings.min_match_score:
                        job_data["status"] = "skipped"

                    # Save to DB
                    job = JobModel(**{
                        k: v for k, v in job_data.items()
                        if k in JobModel.__table__.columns.keys()
                    })
                    db.add(job)
                    await db.flush()
                    jobs_added += 1

                    if score >= 80:
                        job_data["id"] = job.id
                        high_match_jobs.append(job_data)

                except Exception as e:
                    logger.error(f"Failed to process job '{job_data.get('title')}': {e}")
                    continue

            await db.commit()
            logger.info(f"Saved {jobs_added} new jobs. High match: {len(high_match_jobs)}")

            # Notify high-match jobs
            if high_match_jobs:
                await notify_new_jobs(high_match_jobs)

            # Update scheduler run
            await db.execute(
                update(SchedulerRun)
                .where(SchedulerRun.id == run_id)
                .values(
                    status="success",
                    completed_at=datetime.now(timezone.utc),
                    jobs_found=len(all_jobs),
                    jobs_new=jobs_added,
                )
            )
            await db.commit()

        except Exception as e:
            logger.error(f"[Scheduler] {task_name} failed: {e}", exc_info=True)
            await db.execute(
                update(SchedulerRun)
                .where(SchedulerRun.id == run_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    errors=str(e),
                )
            )
            await db.commit()
            from backend.modules.notifier.telegram import notify_error
            await notify_error(task_name, str(e))


# ─── Task: Daily Digest ───────────────────────────────────────────────────────
async def send_daily_digest():
    """Send morning summary via Telegram."""
    async with AsyncSessionLocal() as db:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

        new_today = await db.scalar(
            select(func.count(Job.id)).where(Job.found_at >= today_start)
        )
        high_match = await db.scalar(
            select(func.count(Job.id)).where(
                Job.found_at >= today_start,
                Job.match_score >= 80
            )
        )
        pending_review = await db.scalar(
            select(func.count(Application.id)).where(Application.status == "pending_review")
        )
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        applied_week = await db.scalar(
            select(func.count(Application.id)).where(
                Application.status.in_(["sent", "replied", "interview", "offer"]),
                Application.sent_at >= week_start,
            )
        )

        from backend.modules.notifier.telegram import notify_daily_digest
        await notify_daily_digest({
            "new_today": new_today or 0,
            "high_match": high_match or 0,
            "pending_review": pending_review or 0,
            "applied_week": applied_week or 0,
        })


# ─── Task: Follow-up Checker ──────────────────────────────────────────────────
async def check_follow_ups():
    """Alert about applications that have follow-ups due today."""
    async with AsyncSessionLocal() as db:
        today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

        result = await db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(
                Application.follow_up_due >= today_start,
                Application.follow_up_due <= today,
                Application.status.in_(["sent", "replied"]),
            )
        )
        follow_ups = [
            {"title": job.title, "company": job.company, "id": app.id}
            for app, job in result.fetchall()
        ]

        if follow_ups:
            from backend.modules.notifier.telegram import notify_follow_ups
            await notify_follow_ups(follow_ups)


# ─── Task: Weekly Cleanup ─────────────────────────────────────────────────────
async def cleanup_old_skipped_jobs():
    """Archive/remove skipped jobs older than 30 days."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result = await db.execute(
            select(Job).where(Job.status == "skipped", Job.found_at < cutoff)
        )
        old_jobs = result.scalars().all()
        for job in old_jobs:
            await db.delete(job)
        await db.commit()
        logger.info(f"Cleanup: removed {len(old_jobs)} old skipped jobs.")


# ─── Setup ────────────────────────────────────────────────────────────────────
def setup_scheduler():
    """Register all scheduled tasks."""
    # Scrape every 6 hours
    scheduler.add_job(
        run_scrape_and_score,
        trigger=CronTrigger(hour="0,6,12,18", minute=0),
        id="scrape_and_score",
        replace_existing=True,
        max_instances=1,  # Never run twice simultaneously
        coalesce=True,
    )

    # Daily digest at 9am UTC
    scheduler.add_job(
        send_daily_digest,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_digest",
        replace_existing=True,
    )

    # Follow-up check at 8am UTC
    scheduler.add_job(
        check_follow_ups,
        trigger=CronTrigger(hour=8, minute=0),
        id="follow_up_check",
        replace_existing=True,
    )

    # Weekly cleanup on Sunday at 2am UTC
    scheduler.add_job(
        cleanup_old_skipped_jobs,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_cleanup",
        replace_existing=True,
    )

    logger.info("Scheduler configured with 4 tasks.")
    return scheduler
