"""
api/applications.py — Application tracker endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone, timedelta

from backend.database import get_db
from backend.models import Application, Job, Resume

router = APIRouter(prefix="/api/applications", tags=["applications"])

VALID_STATUSES = [
    "drafted", "pending_review", "approved", "sent",
    "replied", "interview", "offer", "rejected"
]


def _app_to_dict(app: Application, job: Job = None, resume: Resume = None) -> dict:
    return {
        "id": app.id,
        "job_id": app.job_id,
        "resume_id": app.resume_id,
        "status": app.status,
        "cover_message": app.cover_message,
        "email_subject": app.email_subject,
        "tailored_bullets": app.tailored_bullets or [],
        "confidence_score": app.confidence_score,
        "sent_at": app.sent_at.isoformat() if app.sent_at else None,
        "replied_at": app.replied_at.isoformat() if app.replied_at else None,
        "interview_at": app.interview_at.isoformat() if app.interview_at else None,
        "follow_up_due": app.follow_up_due.isoformat() if app.follow_up_due else None,
        "notes": app.notes,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
        "job": {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "url": job.url,
            "role_category": job.role_category,
            "job_type": job.job_type,
            "match_score": job.match_score,
        } if job else None,
        "resume": {
            "id": resume.id,
            "name": resume.name,
            "role_type": resume.role_type,
        } if resume else None,
    }


@router.get("")
async def list_applications(
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List all applications with job and resume info."""
    q = select(Application, Job, Resume).join(
        Job, Application.job_id == Job.id
    ).outerjoin(
        Resume, Application.resume_id == Resume.id
    )

    if status:
        q = q.where(Application.status == status)

    q = q.order_by(desc(Application.updated_at)).offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.fetchall()

    return {
        "applications": [_app_to_dict(app, job, resume) for app, job, resume in rows],
        "total": len(rows),
    }


@router.get("/kanban")
async def kanban_view(db: AsyncSession = Depends(get_db)):
    """Returns applications grouped by status for Kanban view."""
    result = await db.execute(
        select(Application, Job, Resume)
        .join(Job, Application.job_id == Job.id)
        .outerjoin(Resume, Application.resume_id == Resume.id)
        .order_by(desc(Application.updated_at))
    )
    rows = result.fetchall()

    columns = {status: [] for status in VALID_STATUSES}
    for app, job, resume in rows:
        if app.status in columns:
            columns[app.status].append(_app_to_dict(app, job, resume))

    return columns


@router.get("/{app_id}")
async def get_application(app_id: int, db: AsyncSession = Depends(get_db)):
    """Get full application detail."""
    result = await db.execute(
        select(Application, Job, Resume)
        .join(Job, Application.job_id == Job.id)
        .outerjoin(Resume, Application.resume_id == Resume.id)
        .where(Application.id == app_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    app, job, resume = row
    return _app_to_dict(app, job, resume)


@router.patch("/{app_id}")
async def update_application(
    app_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Update application — status, notes, cover_message, follow_up_due.
    Moving to 'approved' → moves to pending_review for manual sending.
    Moving to 'sent' → updates job status to 'applied' and logs memory.
    """
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = app.status
    new_status = payload.get("status")

    if new_status and new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    # Update fields
    if "cover_message" in payload:
        app.cover_message = payload["cover_message"]
    if "email_subject" in payload:
        app.email_subject = payload["email_subject"]
    if "notes" in payload:
        app.notes = payload["notes"]
    if "follow_up_due" in payload:
        try:
            app.follow_up_due = datetime.fromisoformat(payload["follow_up_due"])
        except Exception:
            pass
    if new_status:
        app.status = new_status

        # Side effects
        if new_status == "pending_review" and old_status == "drafted":
            pass  # User manually moves to review — OK

        elif new_status == "sent":
            app.sent_at = datetime.now(timezone.utc)
            # Update job status
            job_result = await db.execute(select(Job).where(Job.id == app.job_id))
            job = job_result.scalars().first()
            if job:
                job.status = "applied"
            # Default follow-up in 7 days
            if not app.follow_up_due:
                app.follow_up_due = datetime.now(timezone.utc) + timedelta(days=7)
            # Log to AI memory
            from backend.modules.ai_engine.memory import record_event
            await record_event(db, "applied", "neutral", app.job_id, app.resume_id)

        elif new_status == "replied":
            app.replied_at = datetime.now(timezone.utc)
            from backend.modules.ai_engine.memory import record_event
            await record_event(db, "replied", "positive", app.job_id, app.resume_id)

        elif new_status == "interview":
            app.interview_at = payload.get("interview_at") or datetime.now(timezone.utc).isoformat()
            from backend.modules.ai_engine.memory import record_event
            await record_event(db, "interviewed", "positive", app.job_id, app.resume_id)

        elif new_status == "offer":
            from backend.modules.ai_engine.memory import record_event
            await record_event(db, "applied", "positive", app.job_id, app.resume_id)

        elif new_status == "rejected":
            from backend.modules.ai_engine.memory import record_event
            await record_event(db, "applied", "negative", app.job_id, app.resume_id)

    app.updated_at = datetime.now(timezone.utc)
    return {"id": app_id, "status": app.status}


@router.delete("/{app_id}")
async def delete_application(app_id: int, db: AsyncSession = Depends(get_db)):
    """Delete any application tracking record completely."""
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Not found")
        
    job_id = app.job_id
    await db.delete(app)
    
    # Also reset the job status back to new so it returns to the pool properly
    job_res = await db.execute(select(Job).where(Job.id == job_id))
    job = job_res.scalars().first()
    if job:
        job.status = "new"
    await db.flush()
    return {"deleted": True}
