"""
content_gen.py — AI content generator using Google Gemini.
Generates tailored cover messages, email subjects, and resume bullets.
Persona-aware, no hallucination policy enforced in prompt.
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Resume, PlatformLink, UserProfile

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)


PERSONA_TONES = {
    "frontend": "Emphasize UI craftsmanship, user experience, performance, and visual excellence. Lead with impact on users.",
    "backend": "Emphasize system architecture, API design, scalability, database efficiency, and reliability.",
    "fullstack": "Emphasize end-to-end ownership, versatility, and the ability to ship complete features independently.",
    "ai": "Emphasize automation, LLM experience, intelligent systems thinking, and measurable efficiency gains.",
    "devops": "Emphasize reliability, uptime, deployment speed, cost reduction, and infrastructure at scale.",
    "freelancer": "Emphasize delivery speed, client outcomes, problem-solving mindset, and proven results.",
    "other": "Emphasize technical skills, impact, and professional growth.",
}


COVER_PROMPT = """You are a precise, professional application writer. Generate a tailored but authentic cover message.

STRICT RULES:
- NEVER fabricate experience, skills, or achievements not in the resume
- NEVER exaggerate. Be honest and confident, not boastful
- Length: 100-200 words
- Tone: {tone_guidance}
- Do not start with "I am writing to..."
- Do not end with "I look forward to hearing from you"
- Reference 2-3 SPECIFIC things from the job description
- Naturally include these links where relevant: {links}

JOB DETAILS:
Title: {title}
Company: {company}
Role Category: {category}
Job Description:
{description}

CANDIDATE PROFILE:
Resume Name: {resume_name}
Role Type: {role_type}
Skills: {skills}
Experience Summary:
{experience_summary}

Return ONLY valid JSON:
{{
  "subject": "<compelling email subject line, under 60 chars>",
  "cover_message_paragraphs": [
    "<paragraph 1>",
    "<paragraph 2>"
  ],
  "tailored_bullets": [
        "<resume bullet 1 — slightly reworded to match job needs (keep factual)>",
    "<resume bullet 2>",
    "<resume bullet 3>"
  ],
  "tone_used": "<one word: professional|friendly|technical|concise>"
}}"""


FREELANCE_PROMPT = """You are an expert at writing winning freelance proposals.

STRICT RULES:
- Be direct - freelance clients are busy
- Lead with the client's problem, then your solution
- Include 1-2 specific results from past work
- Length: 150-200 words
- NEVER fabricate anything not in the resume

PROJECT/JOB:
Title: {title}
Company/Client: {company}  
Description: {description}

YOUR PROFILE:
Skills: {skills}
Experience Summary: {experience_summary}
Links: {links}

Return ONLY valid JSON:
{{
  "subject": "<proposal subject line>",
  "cover_message_paragraphs": [
    "<short, punchy paragraph 1>",
    "<short, punchy paragraph 2>"
  ],
  "tailored_bullets": [],
  "tone_used": "direct"
}}"""


async def _get_platform_links(db: AsyncSession, category: str) -> str:
    """Get relevant platform links for a role category."""
    result = await db.execute(
        select(PlatformLink).where(PlatformLink.is_active == True)
    )
    links = result.scalars().all()
    relevant = [
        f"{link.platform}: {link.url}"
        for link in links
        if not link.relevant_for or category in link.relevant_for
    ]
    return " | ".join(relevant) if relevant else "No links configured yet"


async def generate_application(
    job: Dict[str, Any],
    resume: Any,  # Resume ORM object
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Generate a complete tailored application for a job.
    Returns: {subject, cover_message, tailored_bullets, tone_used}
    """
    category = job.get("role_category", "other")
    is_freelance = job.get("employment_type", "") in ["freelance", "contract"]

    tone_guidance = PERSONA_TONES.get(
        "freelancer" if is_freelance else category,
        PERSONA_TONES["other"]
    )
    links_str = await _get_platform_links(db, category)

    skills_str = ", ".join(resume.skills or []) if resume.skills else "See resume"
    experience = resume.experience_summary or "Not provided"

    # Sanitize inputs for .format() to avoid KeyError on literal braces in JD
    desc_safe = (job.get("description", "") or "").replace("{", "{{").replace("}", "}}")[:2000]
    experience_safe = experience.replace("{", "{{").replace("}", "}}")

    prompt_template = FREELANCE_PROMPT if is_freelance else COVER_PROMPT
    prompt = prompt_template.format(
        title=job.get("title", ""),
        company=job.get("company", "") or "the company",
        category=category,
        description=desc_safe,
        resume_name=resume.name,
        role_type=resume.role_type,
        skills=skills_str,
        experience_summary=experience_safe,
        links=links_str,
        tone_guidance=tone_guidance,
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-flash-latest",
            system_instruction="You are a professional application writer. Always return valid JSON only. No markdown fences. No fabrication.",
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                max_output_tokens=2048,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
        
        # Handle array-based paragraphs fallback gracefully
        cover_msg = result.get("cover_message", "")
        if not cover_msg and "cover_message_paragraphs" in result:
            cover_msg = "\n\n".join(result["cover_message_paragraphs"]).replace("\\n", "\n")
            
        return {
            "subject": result.get("subject", f"Application for {job.get('title', 'Position')}"),
            "cover_message": cover_msg.strip(),
            "tailored_bullets": result.get("tailored_bullets", []),
            "tone_used": result.get("tone_used", "professional"),
        }

    except Exception as e:
        logger.error(f"Content generation failed for '{job.get('title')}': {e}")
        return {
            "subject": f"Application for {job.get('title', 'Position')} at {job.get('company', 'Company')}",
            "cover_message": f"I am very interested in the {job.get('title')} position at {job.get('company', 'your company')}. Please find my resume attached.",
            "tailored_bullets": [],
            "tone_used": "professional",
        }
