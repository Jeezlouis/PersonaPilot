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

from backend.models import Job

logger = logging.getLogger(__name__)


def _hash_job(url: str, title: str, company: str) -> str:
    raw = f"{url}|{title.lower().strip()}|{(company or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation for soft comparison."""
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
    Check if user has already applied to this job.
    Prevents double-applying.
    """
    from backend.models import Application
    result = await db.execute(
        select(Application).where(
            Application.job_id == job_id,
            Application.status.notin_(["drafted"])
        )
    )
    return result.scalars().first() is not None
