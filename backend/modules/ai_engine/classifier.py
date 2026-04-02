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
- "ai": Machine learning, LLMs, data science, NLP, MLOps, automation, RAG
- "devops": Kubernetes, Docker, CI/CD, cloud infrastructure, AWS/GCP/Azure
- "other": PM, design, sales, marketing, non-engineering

CRITICAL RULES:
- Return ONLY valid JSON, no markdown, no explanation
- If unsure between two categories, pick the most dominant
- Never invent categories
- "fullstack" requires BOTH frontend + backend mentions"""

CLASSIFY_TEMPLATE = """Classify this job posting:

Title: {title}
Company: {company}
Description (first 1000 chars): {desc_preview}

Return ONLY this JSON (no markdown):
{{
  "category": "<one of: frontend|backend|fullstack|ai|devops|other>",
  "confidence": <0.0-1.0>,
  "key_signals": ["<up to 5 keywords that drove the decision>"],
  "employment_type": "<full-time|part-time|contract|freelance>",
  "reasoning": "<one sentence>"
}}"""


async def classify_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use Gemini to classify a job's role category.
    Returns dict with category, confidence, key_signals.
    Falls back to rule-based if AI fails.
    """
    title = job.get("title", "")
    company = job.get("company", "") or ""
    desc = job.get("description", "") or ""
    desc_preview = desc[:1000]

    prompt = CLASSIFY_TEMPLATE.format(
        title=title,
        company=company,
        desc_preview=desc_preview,
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
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

        return {
            "category": category,
            "confidence": float(result.get("confidence", 0.5)),
            "key_signals": result.get("key_signals", []),
            "employment_type": result.get("employment_type", "full-time"),
            "reasoning": result.get("reasoning", ""),
        }

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
