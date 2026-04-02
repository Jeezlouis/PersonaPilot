"""
resume_selector.py — Selects the best resume for a given job.
Uses skill overlap + AI confidence scoring.
"""
import logging
import re
from typing import Dict, Any, Optional, List

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Resume

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)

SELECTOR_PROMPT = """You are a resume matching expert. Given a job description and a list of resumes, 
select the BEST resume and explain why. Return ONLY valid JSON.

Job Category: {category}
Job Title: {title}
Key Requirements: {key_signals}
Job Description (preview): {desc_preview}

Available Resumes:
{resumes_list}

Return ONLY this JSON:
{{
  "selected_resume_id": <integer id from the list>,
  "confidence": <0.0-1.0>,
  "reasoning": "<one clear sentence>",
  "match_points": ["<up to 3 points why this resume fits>"]
}}"""


def _skill_overlap(desc: str, skills: List[str]) -> float:
    """Fast keyword overlap score."""
    if not skills:
        return 0.0
    desc_lower = desc.lower()
    matched = sum(1 for s in skills if s.lower() in desc_lower)
    return matched / len(skills)


async def select_best_resume(
    job: Dict[str, Any],
    db: AsyncSession,
) -> Optional[Dict[str, Any]]:
    """
    Select the best resume for this job.
    Returns: {resume_id, resume, confidence, reasoning, match_points}
    """
    category = job.get("role_category", "other")
    desc = job.get("description", "") or ""
    title = job.get("title", "") or ""

    # Load all active resumes
    result = await db.execute(select(Resume).where(Resume.is_active == True))
    resumes = result.scalars().all()

    if not resumes:
        logger.warning("No active resumes found in database.")
        return None

    # Fast path: only one resume
    if len(resumes) == 1:
        return {
            "resume_id": resumes[0].id,
            "resume": resumes[0],
            "confidence": 0.7,
            "reasoning": "Only one resume available.",
            "match_points": [],
        }

    # Step 1: Rule-based pre-filter — exact role_type match gets priority
    exact_matches = [r for r in resumes if r.role_type == category]
    candidates = exact_matches if exact_matches else resumes

    # Step 2: Skill overlap scoring
    scored = []
    for resume in candidates:
        overlap = _skill_overlap(desc, resume.skills or [])
        scored.append((overlap, resume))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = scored[:3]  # top 3 for AI review

    # Step 3: AI final selection (if multiple candidates)
    if len(top_candidates) == 1:
        _, best = top_candidates[0]
        return {
            "resume_id": best.id,
            "resume": best,
            "confidence": top_candidates[0][0],
            "reasoning": "Best skill overlap.",
            "match_points": [],
        }

    resumes_list = "\n".join([
        f"ID {r.id}: {r.name} ({r.role_type}) — Skills: {', '.join((r.skills or [])[:8])}"
        for _, r in top_candidates
    ])

    prompt = SELECTOR_PROMPT.format(
        category=category,
        title=title,
        key_signals=", ".join(job.get("key_signals", [])),
        desc_preview=desc[:800],
        resumes_list=resumes_list,
    )

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=300,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()

        import json
        ai_result = json.loads(raw)
        selected_id = int(ai_result.get("selected_resume_id", top_candidates[0][1].id))

        # Find the resume by ID
        selected_resume = next(
            (r for _, r in top_candidates if r.id == selected_id),
            top_candidates[0][1]
        )
        return {
            "resume_id": selected_resume.id,
            "resume": selected_resume,
            "confidence": float(ai_result.get("confidence", 0.7)),
            "reasoning": ai_result.get("reasoning", ""),
            "match_points": ai_result.get("match_points", []),
        }

    except Exception as e:
        logger.warning(f"AI resume selection failed: {e}. Using top skill overlap.")
        _, best = top_candidates[0]
        return {
            "resume_id": best.id,
            "resume": best,
            "confidence": top_candidates[0][0],
            "reasoning": "Best skill overlap (AI fallback).",
            "match_points": [],
        }
