"""
memory.py — AI memory system.
Records outcomes of past applications to improve future scoring.
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import google.generativeai as genai
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import AIMemory, Job, Application

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)


async def record_event(
    db: AsyncSession,
    event_type: str,
    outcome: str,
    job_id: int,
    resume_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> AIMemory:
    """
    Record a job outcome into AI memory.
    
    event_type: applied, skipped, replied, interviewed, offered, rejected
    outcome: positive (reply/interview/offer), negative (rejected/ghosted), neutral (applied/skipped)
    """
    # Fetch job to extract metadata
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalars().first()

    if not job:
        raise ValueError(f"Job {job_id} not found")

    # Extract keywords from job description for future matching
    desc = job.description or ""
    keywords = _extract_keywords(f"{job.title} {desc}")

    memory = AIMemory(
        event_type=event_type,
        job_id=job_id,
        resume_id=resume_id,
        outcome=outcome,
        keywords=keywords,
        role_category=job.role_category,
        company=job.company,
        created_at=datetime.now(timezone.utc),
        notes=notes,
    )
    db.add(memory)
    await db.flush()
    logger.info(f"Memory recorded: {event_type} → {outcome} for job {job_id}")
    return memory


def _extract_keywords(text: str, top_n: int = 20) -> List[str]:
    """Extract meaningful tech keywords from text."""
    # Simple but effective: extract capitalized words and known tech terms
    tech_pattern = re.compile(
        r'\b(?:React|Vue|Angular|Next\.?js|TypeScript|JavaScript|Python|FastAPI|'
        r'Django|Node\.?js|GraphQL|PostgreSQL|MySQL|MongoDB|Redis|Docker|'
        r'Kubernetes|AWS|GCP|Azure|Git|REST|API|ML|AI|LLM|PyTorch|TensorFlow|'
        r'Tailwind|CSS|HTML|Figma|CI/CD|Terraform|Go|Rust|Java|Kotlin|'
        r'SQLite|Pandas|NumPy|Langchain|OpenAI|Gemini|Full.?Stack|Backend|Frontend)\b',
        re.IGNORECASE
    )
    found = tech_pattern.findall(text)
    # Deduplicate preserving order
    seen = set()
    result = []
    for kw in found:
        normalized = kw.lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(kw)
    return result[:top_n]


async def get_memory_summary(db: AsyncSession) -> Dict[str, Any]:
    """Returns statistics about the memory system."""
    total = await db.scalar(select(func.count(AIMemory.id)))
    positive = await db.scalar(
        select(func.count(AIMemory.id)).where(AIMemory.outcome == "positive")
    )
    negative = await db.scalar(
        select(func.count(AIMemory.id)).where(AIMemory.outcome == "negative")
    )

    # Top engaged companies (positive outcomes)
    result = await db.execute(
        select(AIMemory.company, func.count(AIMemory.id).label("count"))
        .where(AIMemory.outcome == "positive", AIMemory.company.isnot(None))
        .group_by(AIMemory.company)
        .order_by(func.count(AIMemory.id).desc())
        .limit(5)
    )
    top_companies = [{"company": row[0], "count": row[1]} for row in result.fetchall()]

    return {
        "total_events": total or 0,
        "positive_outcomes": positive or 0,
        "negative_outcomes": negative or 0,
        "neutral_outcomes": (total or 0) - (positive or 0) - (negative or 0),
        "top_engaged_companies": top_companies,
    }
