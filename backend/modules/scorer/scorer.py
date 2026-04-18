"""
scorer.py — Job match scoring engine.
Produces a 0-100 score for each job based on 5 weighted factors.
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Resume, AIMemory, UserProfile
from backend.modules.scorer.embeddings import get_embedding, cosine_similarity
from backend.config import settings

logger = logging.getLogger(__name__)


# ─── Weight constants ─────────────────────────────────────────────────────────
WEIGHT_SKILL_MATCH = 0.40
WEIGHT_ROLE_MATCH  = 0.25
WEIGHT_RECENCY     = 0.15
WEIGHT_SALARY      = 0.10
WEIGHT_MEMORY      = 0.10

HALF_LIFE_DAYS = 90


def _tokenize(text: str) -> set:
    """Extract lowercase words from text."""
    return set(re.findall(r"[a-z][a-z0-9+#.]*", text.lower()))


def _detect_seniority(title: str, text: str) -> str:
    """Detect seniority level with a focus on Title first."""
    title_lower = title.lower()
    desc_lower = (text or "").lower()[:2000] # Only check first 2000 chars of desc
    
    # 1. Title Bypass: If title explicitly says junior/mid, it wins
    if any(k in title_lower for k in ["junior", "jr.", "jr ", "entry", "associate", "intern"]):
        return "junior"
    if any(k in title_lower for k in ["mid", "intermediate"]):
        return "mid"
        
    # 2. Check Title for higher seniority
    if any(k in title_lower for k in ["lead", "principal", "staff", "architect", "manager", "head of", "director"]):
        return "lead"
    if any(k in title_lower for k in ["senior", "sr.", "sr ", "expert"]):
        return "senior"

    # 3. Fallback to Description (but only for high seniority words)
    # We check description for senior/lead but with prefix "junior" check first
    if any(k in desc_lower for k in ["lead", "principal", "staff", "architect"]):
        return "lead"
    if any(k in desc_lower for k in ["senior", "expert"]):
        return "senior"
        
    return "mid" # Default to mid if nothing else found


def _decayed_weight(outcome_date: datetime, base_weight: float) -> float:
    """Reduce the influence of old outcomes exponentially (half-life)."""
    import math
    if outcome_date.tzinfo is None:
        outcome_date = outcome_date.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - outcome_date).days
    decay = math.exp(-math.log(2) * max(age_days, 0) / HALF_LIFE_DAYS)
    return base_weight * decay


def _skill_match_score(job_desc: str, resume_skills: List[str]) -> float:
    """
    Measure overlap between job keywords and user skills.
    Returns 0.0 – 1.0.
    """
    if not resume_skills or not job_desc:
        return 0.0
    job_tokens = _tokenize(job_desc)
    matched = sum(1 for skill in resume_skills if skill.lower() in job_tokens)
    return min(matched / max(len(resume_skills), 1), 1.0)


def _role_match_score(job_category: str, preferred_categories: List[str]) -> float:
    """1.0 if job category is in user preferences, 0.5 if 'other', 0.0 if mismatched."""
    if not preferred_categories:
        return 0.7  # no preference = accept all with neutral score
    if job_category in preferred_categories:
        return 1.0
    if job_category == "other":
        return 0.5
    return 0.3


def _recency_score(posted_at: Optional[datetime]) -> float:
    """Score based on how recently the job was posted."""
    if not posted_at:
        return 0.5
    now = datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    age_days = (now - posted_at).days
    if age_days <= 1:
        return 1.0
    elif age_days <= 3:
        return 0.85
    elif age_days <= 7:
        return 0.65
    elif age_days <= 14:
        return 0.40
    return 0.15


def _salary_score(
    salary_min: Optional[float],
    salary_max: Optional[float],
    pref_min: int,
    pref_max: int,
) -> float:
    """Returns how well the salary matches user preference."""
    if salary_min is None and salary_max is None:
        return 0.5  # no info = neutral
    mid = ((salary_min or 0) + (salary_max or (salary_min or 0))) / 2
    if mid <= 0:
        return 0.5
    pref_mid = (pref_min + pref_max) / 2
    ratio = mid / pref_mid
    # Penalize heavily if below min
    if mid < pref_min * 0.7:
        return 0.1
    elif mid < pref_min:
        return 0.4
    elif 0.9 <= ratio <= 1.3:
        return 1.0
    elif ratio > 1.3:
        return 0.85  # above expectations is great
    else:
        return 0.6


def _memory_boost(
    memory_entries: List[Dict],
    job_category: str,
    job_keywords: set,
) -> float:
    """
    Adjust score based on past AI memory outcomes with temporal decay.
    """
    if not memory_entries:
        return 0.5
    total_weight = 0.0
    total_decayed_count = 0.0
    
    for entry in memory_entries:
        if entry["role_category"] != job_category:
            continue
            
        overlap = len(set(entry.get("keywords", [])) & job_keywords)
        if overlap == 0:
            continue
            
        outcome = entry.get("outcome", "neutral")
        raw_val = 1.0 if outcome == "positive" else (-0.5 if outcome == "negative" else 0.5)
        
        # Apply Temporal Decay
        weight = _decayed_weight(entry["created_at"], raw_val)
        total_weight += weight
        total_decayed_count += 1.0 # Or use absolute count for denominator
        
    if total_decayed_count == 0:
        return 0.5
        
    raw = total_weight / total_decayed_count
    return max(0.0, min(1.0, (raw + 1.0) / 2.0))


GLOBAL_HIRE_SIGNALS = [
    "worldwide", "globally", "anywhere in the world",
    "all timezones", "async-first", "fully distributed",
    "open to all locations", "location independent",
    "we hire globally", "international team",
    "using deel", "using remote.com", "using rippling"
]

def _worldwide_boost(text: str) -> float:
    """Check for global-friendly hiring signals and return a score boost."""
    text_lower = (text or "").lower()
    if any(signal in text_lower for signal in GLOBAL_HIRE_SIGNALS):
        return 0.10  # +10 points
    return 0.0

async def score_job(
    job_data: Dict[str, Any],
    db: AsyncSession,
    pref_min: int = 50000,
    pref_max: int = 200000,
) -> float:
    """
    Main scoring function. Implements the 'Expensive Filter' pipeline.
    """
    title = job_data.get("title", "")
    desc = job_data.get("description", "") or ""
    
    # ─── 🏃 Cheap Filter 1: Seniority ──────────────────────────────────────────
    seniority = _detect_seniority(title, desc)
    target_seniorities = settings.target_seniority_list
    if target_seniorities and seniority not in target_seniorities:
        logger.info(f"[Scorer] Filtered by seniority: {title} ({seniority} not in {target_seniorities})")
        return 0.0

    # Fetch all active resumes
    resumes_result = await db.execute(
        select(Resume).where(Resume.is_active == True)
    )
    resumes = resumes_result.scalars().all()

    # Fetch user preferred role categories from profiles
    profiles_result = await db.execute(
        select(UserProfile).where(UserProfile.is_active == True)
    )
    profiles = profiles_result.scalars().all()
    preferred_categories = [p.persona for p in profiles]

    # Fetch recent AI memories
    memory_result = await db.execute(
        select(AIMemory)
    )
    memories = memory_result.scalars().all()
    memory_data = [
        {
            "role_category": m.role_category,
            "keywords": m.keywords or [],
            "outcome": m.outcome,
            "created_at": m.created_at,
        }
        for m in memories
    ]

    job_category = job_data.get("role_category", "other")
    job_tokens = _tokenize(f"{title} {desc}")

    # ─── 🧠 Semantic Skill Match (Expensive) ───────────────────────────────────
    # Phase 3A: Embeddings based match
    if settings.enable_embeddings:
        job_vector = await get_embedding(desc[:2000], job_data.get("hash_id", "temp"), "job")
        skill_scores = []
        for resume in resumes:
            resume_vector = await get_embedding(
                " ".join(resume.skills or []) + " " + (resume.experience_summary or ""), 
                resume.id, 
                "resume"
            )
            skill_scores.append(cosine_similarity(job_vector, resume_vector))
        skill_score = max(skill_scores) if skill_scores else 0.0
    else:
        # Fallback to keyword overlap
        skill_scores = [
            _skill_match_score(desc, resume.skills or [])
            for resume in resumes
        ]
        skill_score = max(skill_scores) if skill_scores else 0.0

    role_score = _role_match_score(job_category, preferred_categories)
    recency_score = _recency_score(job_data.get("posted_at"))
    salary_score = _salary_score(
        job_data.get("salary_min"),
        job_data.get("salary_max"),
        pref_min,
        pref_max,
    )
    memory_score = _memory_boost(memory_data, job_category, job_tokens)
    worldwide_boost = _worldwide_boost(desc)

    raw_score = (
        WEIGHT_SKILL_MATCH * skill_score
        + WEIGHT_ROLE_MATCH * role_score
        + WEIGHT_RECENCY * recency_score
        + WEIGHT_SALARY * salary_score
        + WEIGHT_MEMORY * memory_score
        + worldwide_boost # Direct addition for specific signals
    )

    final_score = round(raw_score * 100, 1)
    logger.debug(
        f"Score: {final_score} | skill={skill_score:.2f} role={role_score:.2f} "
        f"recency={recency_score:.2f} salary={salary_score:.2f} memory={memory_score:.2f} world={worldwide_boost:.2f}"
    )
    return final_score
