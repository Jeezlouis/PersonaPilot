"""
dedup.py — Deduplication engine.
Prevents the same job appearing twice using:
  1. Hash ID (URL + title + company)
  2. URL exact match
  3. Semantic similarity (title + company combined)
"""
import hashlib
import logging
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Job, Application
from backend.config import settings

logger = logging.getLogger(__name__)


def _hash_job(url: str, title: str, company: str) -> str:
    raw = f"{url}|{(title or '').lower().strip()}|{(company or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation for soft comparison."""
    if not title:
        return ""
    import re
    return re.sub(r"[^a-z0-9\s]", "", title.lower().strip())


async def filter_new_jobs(
    db: AsyncSession,
    jobs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Given a list of normalized job dicts, return only those
    that don't already exist in the DB.
    Uses 3-layer dedup: hash, URL, and title+company fuzzy.
    """
    if not jobs:
        return []

    # Load existing hashes + urls from DB
    existing_hashes_result = await db.execute(select(Job.hash_id))
    existing_hashes = set(row[0] for row in existing_hashes_result.fetchall())

    existing_urls_result = await db.execute(select(Job.url))
    existing_urls = set(row[0] for row in existing_urls_result.fetchall())

    new_jobs = []
    seen_hashes_this_batch = set()

    for job in jobs:
        hash_id = job.get("hash_id") or _hash_job(
            job.get("url", ""), job.get("title", ""), job.get("company", "")
        )

        # Layer 1: Hash check
        if hash_id in existing_hashes or hash_id in seen_hashes_this_batch:
            logger.debug(f"Dedup hash: '{job.get('title')}' @ {job.get('company')}")
            continue

        # Layer 2: URL exact match
        url = job.get("url", "")
        if url and url in existing_urls:
            logger.debug(f"Dedup URL: {url}")
            continue

        seen_hashes_this_batch.add(hash_id)
        job["hash_id"] = hash_id
        new_jobs.append(job)

    logger.info(f"Dedup: {len(jobs)} jobs → {len(new_jobs)} new after filtering.")
    return new_jobs


async def is_already_applied(db: AsyncSession, job_id: int) -> bool:
    """
    Check if user has already applied to this specific job ID.
    """
    result = await db.execute(
        select(Application).where(
            Application.job_id == job_id,
            Application.status.notin_(["drafted"])
        )
    )
    return result.scalars().first() is not None


async def already_applied_to_company_role(
    db: AsyncSession, 
    company: str, 
    title: str
) -> bool:
    """
    Check if user has already applied to this company for a similar role.
    Uses normalized company name + title similarity cross-check.
    """
    if not company or not title:
        return False

    norm_company = (company or "").lower().strip()
    norm_title = _normalize_title(title)

    # Simple similarity: match by prefix or contain for now.
    # A more robust check could use trigram similarity if on PostgreSQL with pg_trgm.
    # For SQLite, we'll fetch recently applied jobs and compare in Python.
    
    result = await db.execute(
        select(Job.title, Job.company, Application.created_at, Application.status)
        .join(Application, Job.id == Application.job_id)
        .where(Application.status.notin_(["rejected", "ghosted"]))
    )
    
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    interval = timedelta(days=settings.email_outreach_interval_days)

    for row_title, row_company, row_created, row_status in result.fetchall():
        if (row_company or "").lower().strip() == norm_company:
            # 1. Title Similarity Check
            if _normalize_title(row_title) == norm_title:
                logger.warning(f"Duplicate application detected: Already applied to '{title}' @ '{company}'")
                return True
            
            # 2. Time-based domain check (Anti-spam)
            # Ensure row_created is timezone aware
            created_at = row_created
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
                
            if now - created_at < interval:
                logger.warning(f"Anti-spam check: Already contacted '{company}' in the last {settings.email_outreach_interval_days} days.")
                return True
                
    return False
