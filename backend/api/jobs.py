"""
api/jobs.py — Jobs endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime, timezone, timedelta

from backend.database import get_db
from backend.models import Job, Application

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "url": job.url,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "job_type": job.job_type,
        "employment_type": job.employment_type,
        "role_category": job.role_category,
        "description": job.description,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "found_at": job.found_at.isoformat() if job.found_at else None,
        "status": job.status,
        "match_score": job.match_score,
        "tags": job.tags or [],
    }


@router.get("")
async def list_jobs(
    status: Optional[str] = Query(None),
    role_category: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    min_score: float = Query(0),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    sort_by: str = Query("match_score"),
    db: AsyncSession = Depends(get_db),
):
    """List jobs with filtering and pagination."""
    q = select(Job)

    if status:
        q = q.where(Job.status == status)
    else:
        # Default: exclude skipped
        q = q.where(Job.status != "skipped")

    if role_category:
        q = q.where(Job.role_category == role_category)
    if job_type:
        q = q.where(Job.job_type == job_type)
    if min_score > 0:
        q = q.where(Job.match_score >= min_score)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q)

    # Sort
    sort_col = getattr(Job, sort_by, Job.match_score)
    q = q.order_by(desc(sort_col)).offset(offset).limit(limit)

    result = await db.execute(q)
    jobs = result.scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "jobs": [_job_to_dict(j) for j in jobs],
    }


@router.get("/stats")
async def job_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard statistics."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    week_start = datetime.now(timezone.utc) - timedelta(days=7)

    total = await db.scalar(select(func.count(Job.id)))
    new_today = await db.scalar(
        select(func.count(Job.id)).where(Job.found_at >= today_start)
    )
    high_match = await db.scalar(
        select(func.count(Job.id)).where(Job.match_score >= 80, Job.status != "skipped")
    )
    applied = await db.scalar(
        select(func.count(Application.id)).where(
            Application.status.in_(["sent", "replied", "interview", "offer"])
        )
    )
    interviews = await db.scalar(
        select(func.count(Application.id)).where(Application.status == "interview")
    )
    pending_review = await db.scalar(
        select(func.count(Application.id)).where(Application.status == "pending_review")
    )

    # Category breakdown
    cat_result = await db.execute(
        select(Job.role_category, func.count(Job.id))
        .where(Job.status != "skipped")
        .group_by(Job.role_category)
    )
    categories = {row[0]: row[1] for row in cat_result.fetchall()}

    # Top companies
    top_result = await db.execute(
        select(Job.company, func.count(Job.id).label("count"))
        .where(Job.status != "skipped", Job.company.isnot(None))
        .group_by(Job.company)
        .order_by(func.count(Job.id).desc())
        .limit(5)
    )
    top_companies = [{"company": r[0], "count": r[1]} for r in top_result.fetchall()]

    return {
        "total_jobs": total or 0,
        "new_today": new_today or 0,
        "high_match_count": high_match or 0,
        "total_applied": applied or 0,
        "interviews": interviews or 0,
        "pending_review": pending_review or 0,
        "categories": categories,
        "top_companies": top_companies,
    }


@router.get("/{job_id}")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single job with full details."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dict = _job_to_dict(job)

    # Check if application exists
    app_result = await db.execute(
        select(Application).where(Application.job_id == job_id)
        .order_by(desc(Application.created_at))
        .limit(1)
    )
    app = app_result.scalars().first()
    job_dict["application"] = None
    if app:
        job_dict["application"] = {
            "id": app.id,
            "status": app.status,
            "cover_message": app.cover_message,
            "email_subject": app.email_subject,
            "tailored_bullets": app.tailored_bullets,
            "confidence_score": app.confidence_score,
            "created_at": app.created_at.isoformat() if app.created_at else None,
        }

    return job_dict


@router.patch("/{job_id}/status")
async def update_job_status(
    job_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update job status (reviewed, shortlisted, skipped)."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    valid_statuses = ["new", "reviewed", "shortlisted", "skipped"]
    new_status = payload.get("status")
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    job.status = new_status
    return {"id": job_id, "status": new_status}


@router.post("/{job_id}/draft")
async def draft_application(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    AI-generate a tailored application draft for this job.
    Does NOT submit anything — creates a draft for review.
    """
    from backend.modules.ai_engine.resume_selector import select_best_resume
    from backend.modules.ai_engine.content_gen import generate_application
    from backend.modules.deduplicator.dedup import is_already_applied
    from backend.modules.notifier.telegram import notify_application_drafted

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Safety: check not already applied
    already = await is_already_applied(db, job_id)
    if already:
        raise HTTPException(status_code=409, detail="Already applied to this job.")

    job_dict = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "role_category": job.role_category,
        "employment_type": job.employment_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "url": job.url,
    }

    # Select best resume
    resume_selection = await select_best_resume(job_dict, db)
    if not resume_selection:
        raise HTTPException(status_code=400, detail="No active resumes found. Add resumes in Settings.")

    resume = resume_selection["resume"]

    # Generate content
    content = await generate_application(job_dict, resume, db)

    # Save application draft
    app = Application(
        job_id=job_id,
        resume_id=resume.id,
        status="drafted",
        cover_message=content["cover_message"],
        email_subject=content["subject"],
        tailored_bullets=content["tailored_bullets"],
        confidence_score=resume_selection["confidence"],
        notes=f"AI reasoning: {resume_selection['reasoning']}",
    )
    db.add(app)
    await db.flush()

    # Update job status
    job.status = "shortlisted"

    await notify_application_drafted(job.title, job.company or "Company", resume.name)

    return {
        "application_id": app.id,
        "resume": {"id": resume.id, "name": resume.name, "role_type": resume.role_type},
        "confidence": resume_selection["confidence"],
        "reasoning": resume_selection["reasoning"],
        "subject": content["subject"],
        "cover_message": content["cover_message"],
        "tailored_bullets": content.get("tailored_bullets", []),
    }
