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
from backend.modules.scorer.embeddings import get_embedding, cosine_similarity
from datetime import datetime, timezone, timedelta

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

    # ─── Step 1: Semantic Pre-Scoring ──────────────────────────────────────────
    scored = []
    
    # Get Job Embedding
    job_vector = []
    if settings.enable_embeddings:
        job_vector = await get_embedding(desc[:2000], job.get("hash_id", "temp"), "job")

    for resume in resumes:
        # A. Semantic Score (0.7 weight)
        if settings.enable_embeddings:
            resume_vector = await get_embedding(
                " ".join(resume.skills or []) + " " + (resume.experience_summary or ""), 
                resume.id, 
                "resume"
            )
            semantic_score = cosine_similarity(job_vector, resume_vector)
        else:
            semantic_score = _skill_overlap(desc, resume.skills or [])
            
        # B. Persona Match (0.2 weight)
        persona_score = 1.0 if resume.role_type == category else 0.5
        
        # C. Recency Bonus (0.1 weight)
        recency_bonus = 0.0
        if resume.updated_at:
            if (datetime.now(timezone.utc) - resume.updated_at.replace(tzinfo=timezone.utc)).days < 30:
                recency_bonus = 1.0
        
        total_score = (0.7 * semantic_score) + (0.2 * persona_score) + (0.1 * recency_bonus)
        scored.append((total_score, resume))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = scored[:3]  # top 3 for AI review

    # Step 2: AI final selection
    if len(top_candidates) == 1:
        score_val, best = top_candidates[0]
        return {
            "resume_id": best.id,
            "resume": best,
            "confidence": score_val,
            "reasoning": "Best semantic match.",
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
        from backend.modules.ai_engine.throttler import gemini_throttler
        await gemini_throttler.throttle()

        model = genai.GenerativeModel("models/gemini-flash-latest")
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
