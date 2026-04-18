"""
classifier.py — AI-powered job type classifier using Google Gemini.
Classifies jobs into: frontend, backend, fullstack, ai, devops, other.
"""
import json
import logging
import re
from typing import Dict, Any

import google.generativeai as genai

from backend.config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)

VALID_CATEGORIES = {"frontend", "backend", "fullstack", "ai", "devops", "other"}

SYSTEM_PROMPT = """You are a precise job classification AI. Analyze job postings and return ONLY valid JSON.

Categories:
- "frontend": React, Vue, Angular, Next.js, CSS, UI/UX, Tailwind, design systems
- "backend": APIs, Node, Python, Go, databases, server-side, microservices
- "fullstack": Requires both frontend AND backend skills
- "not_software": Use this for roles that are NOT primarily software engineering.
  * ALWAYS reject: Restoration, Remediation, Construction, Civil Engineering, Cleaning, Manual Labor, Truck Driver, Nurse, Sales (non-tech), HR, Handyman.
  * Consultant roles are only software if they explicitly mention coding (Python, JS, etc).

CRITICAL RULES:
- Return ONLY valid JSON, no markdown, no explanation
- A role is "not_software" if writing code is not the primary daily activity.
- If unsure, "not_software" is the safest choice.
- If the words "Restoration" or "Remediation" appear, it is ALWAYS "not_software".
"""

CLASSIFY_TEMPLATE = """Classify this job posting:

Title: {title}
Company: {company}
Description (first 1000 chars): {desc_preview}

Return ONLY this JSON (no markdown):
{{
  "category": "<one of: frontend|backend|fullstack|ai|devops|not_software>",
  "confidence": <0.0-1.0>,
  "key_signals": ["<up to 5 keywords that drove the decision>"],
  "employment_type": "<full-time|part-time|contract|freelance>",
  "reasoning": "<one sentence>"
}}"""


from backend.modules.ai_engine.throttler import gemini_throttler
from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.ai_engine.cache import get_cached_ai_result, set_cached_ai_result

async def classify_job(job: Dict[str, Any], db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """
    Use Gemini to classify a job's role category.
    Returns dict with category, confidence, key_signals.
    Falls back to rule-based if AI fails.
    """
    title = job.get("title", "")
    company = job.get("company", "") or ""
    desc = job.get("description", "") or ""
    desc_preview = desc[:1000]
    hash_id = job.get("hash_id")

    # 1. Check Cache
    if db and hash_id:
        cached = await get_cached_ai_result(db, f"classify:{hash_id}")
        if cached:
            return cached

    prompt = CLASSIFY_TEMPLATE.format(
        title=title,
        company=company,
        desc_preview=desc_preview,
    )

    try:
        # Rate Limit
        await gemini_throttler.throttle()

        model = genai.GenerativeModel(
            model_name="models/gemini-flash-latest",
            system_instruction=SYSTEM_PROMPT,
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=300,
            ),
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
        category = result.get("category", "other").lower()
        if category not in VALID_CATEGORIES:
            category = "other"

        final_res = {
            "category": category,
            "confidence": float(result.get("confidence", 0.5)),
            "key_signals": result.get("key_signals", []),
            "employment_type": result.get("employment_type", "full-time"),
            "reasoning": result.get("reasoning", ""),
        }

        # 2. Save Cache
        if db and hash_id:
            await set_cached_ai_result(db, f"classify:{hash_id}", final_res)

        return final_res

    except Exception as e:
        logger.warning(f"Gemini classify failed for '{title}': {e}. Using rule-based fallback.")
        # Fallback: use the normalizer's rule-based detection
        from backend.modules.scraper.normalizer import detect_role_category, detect_employment_type
        category = job.get("role_category") or detect_role_category(f"{title} {desc}")
        employment = job.get("employment_type") or detect_employment_type(f"{title} {desc}")
        return {
            "category": category,
            "confidence": 0.4,
            "key_signals": [],
            "employment_type": employment,
            "reasoning": "Rule-based fallback (AI unavailable)",
        }
