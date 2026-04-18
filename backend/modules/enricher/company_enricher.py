"""
company_enricher.py — Gathers deep intelligence about a company.
Injects context into AI generation for hyper-tailored applications.
"""
import logging
import json
from typing import Dict, Any, Optional

import google.generativeai as genai
from backend.config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)

ENRICH_SYSTEM_PROMPT = """You are a corporate research assistant. 
Given a company name and job title, provide a concise brief including:
1. "about": 2-3 sentences on what they actually do/their mission
2. "recent_news": Any major recent events (acquisitions, funding, launches)
3. "tech_stack": Likely technologies they use based on the job and your knowledge
4. "culture_signals": What they value (e.g., speed, innovation, work-life balance)

Return ONLY valid JSON."""

ENRICH_PROMPT = """Research and enrich info for:
Company: {company}
Role: {title}

Return ONLY this JSON:
{{
  "about": "...",
  "recent_news": "...",
  "tech_stack": ["...", "..."],
  "culture_signals": ["...", "..."]
}}"""

async def enrich_company_info(company: str, title: str) -> Dict[str, Any]:
    """
    Use Gemini's internal knowledge to enrich company context.
    In the future, this can be expanded with real-time Google Search/Serper.
    """
    if not settings.enable_enrichment or not company:
        return {
            "about": "",
            "recent_news": "No recent news found.",
            "tech_stack": [],
            "culture_signals": []
        }

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            system_instruction=ENRICH_SYSTEM_PROMPT
        )
        
        response = await model.generate_content_async(
            ENRICH_PROMPT.format(company=company, title=title),
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json",
            )
        )
        
        result = json.loads(response.text.strip())
        logger.info(f"[Enricher] Successfully enriched context for {company}")
        return result

    except Exception as e:
        logger.warning(f"[Enricher] Failed to enrich {company}: {e}")
        return {
            "about": f"{company} is a company in the tech space.",
            "recent_news": "N/A",
            "tech_stack": [],
            "culture_signals": []
        }
