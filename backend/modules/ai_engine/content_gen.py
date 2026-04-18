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
from backend.modules.enricher.company_enricher import enrich_company_info

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


COVER_PROMPT = """You are writing a cover letter on behalf of {candidate_name}, a versatile mid-level software engineer based in Nigeria targeting remote-first international roles.

CANDIDATE PROFILE (Use this as your only source of truth for experience):
{experience_summary}

JOB DETAILS:
- Company: {company}
- Role: {title}
- Description: {description}
- Company intel (if available): {company_intel}

VOICE & TONE RULES:
- Write in first person as the candidate. Sound like a sharp, confident young engineer who knows their worth but isn't arrogant.
- Conversational but professional — like a smart email from a real person, not a formal letter.
- NO BUZZWORDS. Never use: passionate, dynamic, leverage, synergy, delighted, excited to apply, hard-working, team player, fast learner.
- Never open with "I am writing to apply for..." or "I came across this opportunity..."
- Never end with "I look forward to hearing from you" or any variation of it.
- No filler sentences. Every sentence must earn its place.

STRICT OPENING LINE RULE: The first sentence must be about the candidate or their work — NOT about what the company needs. Never restate the job description. If your opening line could have been written by reading only the job posting, rewrite it. Start with YOUR entry into their world.

STRUCTURE (follow this exactly, no headers):
1. Opening line — start with a specific observation about the company, the role, or a problem they're clearly trying to solve. One sentence. Make it specific enough that it could only apply to THIS company.
2. Middle paragraph — connect 2-3 of the candidate's most relevant experiences or projects directly to what the job needs. Be concrete: name the tech, name the outcome, name the scale where possible. If PersonaPilot (this AI automation project) is relevant, reference it naturally.
3. Closing paragraph — one short paragraph. State clearly that you are based in Nigeria, work fully remote, and are available on WAT/EST/CET overlap. Be matter-of-fact about it, not apologetic. End with one specific question about the role that shows genuine curiosity.

FORMAT:
- Total length: 180-220 words maximum. Plain paragraphs.
- Completion check: Ensure the message ends with a clear closing and doesn't cut off mid-sentence.
- Return ONLY valid JSON with keys: "subject" and "cover_message".

QUALITY CHECK PROMPT:
Review the following cover letter and return a JSON object: {{"passes": true/false, "issues": []}}.
Fail (passes: false) if:
- Opens with a description of what the company needs first.
- Contains buzzwords like passionate, leverage, synergy, delighted, dynamic.
- Is cut off or incomplete.
- Longer than 220 words.
- Sentence starts with "I am writing to..."."""


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

    # ─── Company Enrichment ────────────────────────────────────────────────────
    intel = await enrich_company_info(job.get("company", ""), job.get("title", ""))
    intel_str = f"About: {intel.get('about')}\nNews: {intel.get('recent_news')}\nTech Stack: {', '.join(intel.get('tech_stack', []))}"
    intel_safe = intel_str.replace("{", "{{").replace("}", "}}")

    desc_safe = job.get("description", "").replace("{", "{{").replace("}", "}}")
    experience_safe = experience.replace("{", "{{").replace("}", "}}")

    prompt_template = FREELANCE_PROMPT if is_freelance else COVER_PROMPT
    prompt = prompt_template.format(
        candidate_name=resume.name,
        title=job.get("title", ""),
        company=job.get("company", "") or "the company",
        category=category,
        description=desc_safe,
        company_intel=intel_safe,
        experience_summary=experience_safe,
        skills=skills_str,
        links=links_str,
        tone_guidance=tone_guidance,
    )

    max_retries = 2
    last_error = ""
    
    for attempt in range(max_retries + 1):
        try:
            model = genai.GenerativeModel(
                model_name="models/gemini-flash-latest"
            )
            
            from backend.modules.ai_engine.throttler import gemini_throttler
            
            current_prompt = prompt
            if attempt > 0:
                current_prompt += f"\n\nCRITICAL FIX NEEDED: Your previous response failed quality checks. Ensure you start with a sentence ABOUT YOU and avoid all buzzwords. Do not use markdown backticks."

            await gemini_throttler.throttle()
            response = model.generate_content(
                current_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7 + (attempt * 0.1),
                    max_output_tokens=2048,
                ),
            )
            
            raw_text = response.text.strip()
            
            # 1. Fuzzy JSON Extraction (find the outermost { })
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1:
                clean_json = raw_text[start:end+1]
                # Fix common JSON errors from AI (like raw newlines in strings)
                # We can't easily fix all, but let's try a safe approach
                try:
                    result = json.loads(clean_json)
                except:
                    # If strict JSON fails, try cleaning it up
                    clean_json = re.sub(r'(\w+):\s*"', r'"\1": "', clean_json) # Ensure keys are quoted
                    result = json.loads(clean_json, strict=False)
            else:
                # Fallback: Maybe it just gave the text?
                if len(raw_text) > 200:
                    result = {"cover_message": raw_text, "subject": f"Application for {job.get('title')}"}
                else:
                    raise ValueError("No JSON or long text found in AI response.")

            # Extraction
            cover_msg = result.get("cover_message", "")
            if not cover_msg and "cover_message_paragraphs" in result:
                paras = result["cover_message_paragraphs"]
                cover_msg = "\n\n".join(paras) if isinstance(paras, list) else str(paras)
            
            if not cover_msg or len(str(cover_msg)) < 80:
                raise ValueError("Message too short or empty.")

            # ─── Quality Check Gate ──────────────────────────────────────────
            qc_model = genai.GenerativeModel("models/gemini-flash-latest")
            qc_prompt = f"""Review this cover letter for a Mid-Level Software Engineer role.
Rules:
1. First sentence must be about the candidate, NOT what the company needs.
2. NO buzzwords (passionate, leverage, synergy, etc).
3. No opening with "I am writing to apply...".
4. Must not be cut off.

Return JSON ONLY: {{"passes": true/false, "issues": ["..."]}}

Letter:
{cover_msg}
"""
            await gemini_throttler.throttle()
            qc_resp = qc_model.generate_content(qc_prompt)
            qc_data = {}
            try:
                qc_clean = re.sub(r"^```(?:json)?\s*", "", qc_resp.text.strip())
                qc_clean = re.sub(r"\s*```$", "", qc_clean)
                qc_data = json.loads(qc_clean)
            except:
                qc_data = {"passes": True} # Fallback if QC fails

            if not qc_data.get("passes", True) and attempt < max_retries:
                issues_str = ", ".join(qc_data.get("issues", []))
                logger.warning(f"QC Failed for '{job.get('title')}': {issues_str}. Retrying...")
                prompt += f"\n\nYOUR PREVIOUS ATTEMPT FAILED QUALITY CONTROL. Issues: {issues_str}. Fix these immediately."
                continue

            return {
                "subject": result.get("subject", f"Application for {job.get('title', 'Position')}"),
                "cover_message": str(cover_msg).strip(),
                "tailored_bullets": result.get("tailored_bullets", []),
                "tone_used": result.get("tone_used", "professional"),
            }

        except Exception as e:
            last_error = str(e)
            raw_content = response.text if 'response' in locals() and hasattr(response, 'text') else 'No response text'
            logger.error(f"[Attempt {attempt+1}] AI Generation Error: {e}")
            logger.debug(f"[Attempt {attempt+1}] Raw Response: {raw_content}")
            continue

    # Final fallback if all retries fail
    logger.error(f"All {max_retries + 1} AI attempts failed for '{job.get('title')}'. Falling back to template. Error: {last_error}")
    company_name = job.get("company")
    if not company_name or "rss" in company_name.lower():
        company_name = "the hiring team"
        
    return {
        "subject": f"Application: {job.get('title', 'Software Engineer')}",
        "cover_message": f"I'm reaching out regarding the {job.get('title', 'open')} position. Given my background in {category} development and experience with {skills_str[:60]}, I believe my profile aligns well with what your team is looking for. I've attached my resume and would welcome the chance to discuss how I can contribute to your goals at {company_name}.",
        "tailored_bullets": [],
        "tone_used": "professional",
    }
