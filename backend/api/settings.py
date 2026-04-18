"""
api/settings.py — Settings endpoints.
Manages platform links, user profiles/personas, and system config.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import PlatformLink, UserProfile
from backend.config import settings
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/settings", tags=["settings"])

router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_PLATFORMS = ["github", "portfolio", "linkedin", "upwork", "fiverr", "other"]
VALID_PERSONAS = ["frontend", "backend", "fullstack", "ai", "devops", "freelancer", "other"]


# ─── Platform Links ────────────────────────────────────────────────────────────

@router.get("/links")
async def get_links(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlatformLink))
    links = result.scalars().all()
    return {"links": [
        {
            "id": l.id,
            "platform": l.platform,
            "url": l.url,
            "description": l.description,
            "relevant_for": l.relevant_for or [],
            "is_active": l.is_active,
        }
        for l in links
    ]}


@router.post("/links")
async def create_link(payload: dict, db: AsyncSession = Depends(get_db)):
    platform = payload.get("platform", "other").lower()
    if platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")

    link = PlatformLink(
        platform=platform,
        url=payload.get("url", ""),
        description=payload.get("description", ""),
        relevant_for=payload.get("relevant_for", []),
        is_active=payload.get("is_active", True),
    )
    db.add(link)
    await db.flush()
    return {"id": link.id, "platform": link.platform, "url": link.url}


@router.put("/links/{link_id}")
async def update_link(link_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlatformLink).where(PlatformLink.id == link_id))
    link = result.scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    for field in ["url", "description", "relevant_for", "is_active", "platform"]:
        if field in payload:
            setattr(link, field, payload[field])
    return {"id": link.id, "updated": True}


@router.delete("/links/{link_id}")
async def delete_link(link_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlatformLink).where(PlatformLink.id == link_id))
    link = result.scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)
    return {"deleted": True}


# ─── User Profiles / Personas ─────────────────────────────────────────────────

@router.get("/personas")
async def get_personas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile))
    profiles = result.scalars().all()
    return {"personas": [
        {
            "id": p.id,
            "persona": p.persona,
            "tone_guidance": p.tone_guidance,
            "preferred_keywords": p.preferred_keywords or [],
            "avoided_keywords": p.avoided_keywords or [],
            "is_active": p.is_active,
            "priority": p.priority,
        }
        for p in profiles
    ]}


@router.post("/personas")
async def create_persona(payload: dict, db: AsyncSession = Depends(get_db)):
    persona = payload.get("persona", "other").lower().strip()
    if not persona:
        raise HTTPException(status_code=400, detail=f"Persona name cannot be empty")

    profile = UserProfile(
        persona=persona,
        tone_guidance=payload.get("tone_guidance", ""),
        preferred_keywords=payload.get("preferred_keywords", []),
        avoided_keywords=payload.get("avoided_keywords", []),
        is_active=payload.get("is_active", True),
        priority=payload.get("priority", 5),
    )
    db.add(profile)
    await db.flush()
    return {"id": profile.id, "persona": profile.persona}


@router.put("/personas/{profile_id}")
async def update_persona(profile_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).where(UserProfile.id == profile_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Persona not found")
    for field in ["tone_guidance", "preferred_keywords", "avoided_keywords", "is_active", "priority"]:
        if field in payload:
            setattr(profile, field, payload[field])
    return {"id": profile.id, "updated": True}


@router.delete("/personas/{profile_id}")
async def delete_persona(profile_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).where(UserProfile.id == profile_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(profile)
    return {"deleted": True}


# ─── Trigger Manual Actions ───────────────────────────────────────────────────

@router.post("/scrape-now")
async def trigger_scrape():
    """Manually trigger a scrape run."""
    from backend.scheduler import run_scrape_and_score
    import asyncio
    asyncio.create_task(run_scrape_and_score())
    return {"message": "Scrape started in background."}


@router.post("/test-telegram")
async def test_telegram():
    """Send a test Telegram message."""
    from backend.modules.notifier.telegram import test_connection
    success = await test_connection()
    if success:
        return {"message": "Telegram connected! Check your chat."}
    raise HTTPException(status_code=500, detail="Telegram not configured or unreachable.")

@router.post("/rescore-jobs")
async def trigger_rescore():
    """Manually trigger a rescoring of all jobs based on current resumes."""
    from backend.database import AsyncSessionLocal
    from backend.models import Job
    from backend.modules.scorer.scorer import score_job
    from backend.config import settings as app_settings
    import asyncio

    async def rescore_background():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Job))
            jobs = result.scalars().all()
            for job in jobs:
                job_dict = {
                    "title": job.title,
                    "description": job.description,
                    "role_category": job.role_category,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                    "posted_at": job.posted_at
                }
                new_score = await score_job(job_dict, db, pref_min=app_settings.salary_min, pref_max=app_settings.salary_max)
                job.match_score = new_score
                
                # Unskip if it now matches
                if job.status == "skipped" and new_score >= app_settings.min_match_score:
                    job.status = "new"
                # Reskip if it lost match
                elif job.status == "new" and new_score < app_settings.min_match_score:
                    job.status = "skipped"
                    
            await db.commit()

    asyncio.create_task(rescore_background())
    return {"message": "Rescoring started in background... Refresh dashboard in 5 seconds."}
# ─── Global System Config ───────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    candidate_first_name: Optional[str] = None
    candidate_last_name: Optional[str] = None
    candidate_email: Optional[str] = None
    candidate_phone: Optional[str] = None
    candidate_linkedin: Optional[str] = None
    candidate_github: Optional[str] = None
    scrape_mode: Optional[str] = None
    salary_minimum: Optional[int] = None
    target_seniority: Optional[str] = None
    enable_embeddings: Optional[bool] = None
    enable_enrichment: Optional[bool] = None

@router.get("/config")
async def get_config():
    """Retrieve the current running configuration."""
    return {
        "candidate_first_name": settings.candidate_first_name,
        "candidate_last_name": settings.candidate_last_name,
        "candidate_email": settings.candidate_email,
        "candidate_phone": settings.candidate_phone,
        "candidate_linkedin": settings.candidate_linkedin,
        "candidate_github": settings.candidate_github,
        "scrape_mode": settings.scrape_mode,
        "salary_minimum": settings.salary_minimum,
        "target_seniority": settings.target_seniority,
        "enable_embeddings": settings.enable_embeddings,
        "enable_enrichment": settings.enable_enrichment,
    }

@router.patch("/config")
async def update_config(payload: ConfigUpdate):
    """
    Update the running configuration. 
    Note: These changes persist only for the current session.
    To make them permanent, update your .env file.
    """
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    return {"status": "updated", "config": update_data}
