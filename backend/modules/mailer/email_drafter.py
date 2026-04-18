import logging
import json
import re
from typing import Dict, Any
import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.models import Resume, PlatformLink

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)

DRAFT_PROMPT = """You are drafting a cold email application on behalf of {candidate_name}, a mid-level software engineer based in Nigeria looking for remote roles.

CANDIDATE INFO:
{experience_summary}

JOB INFO:
- Company: {company}
- Role: {title}
- Description: {description}
- Company intel: {company_intel}

RULES:
- Limit response to a maximum of 150 words. Be remarkably concise.
- Provide a subject line separately in the JSON. Format: "[Role] — [Specific company hook]"
- Do not include the subject line in the body.
- Be polite, direct, and conversational.
- Mention availability (remote/overlap) seamlessly.
- STRICT OPENING LINE RULE: The first sentence must be about YOU (the candidate) or your work. Never restate the job or summarize what the company needs first.
- Completion check: Ensure the message doesn't end mid-sentence.

Return JSON EXACTLY like this:
{{
  "subject": "...",
  "body": "..."
}}
"""

async def generate_email_draft(job: Dict[str, Any], resume: Resume, db: AsyncSession, company_intel: str = "") -> Dict[str, str]:
    desc = job.get("description", "")[:1000]
    
    prompt = DRAFT_PROMPT.format(
        candidate_name=resume.name,
        company=job.get("company", "the company"),
        title=job.get("title", ""),
        description=desc,
        company_intel=company_intel,
        experience_summary=resume.experience_summary[:1000] if resume.experience_summary else ""
    )
    
    try:
        model = genai.GenerativeModel(
            model_name="models/gemini-flash-latest",
            system_instruction="You are a precise cold email writer. Output only JSON."
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.7, max_output_tokens=600)
        )
        
        raw_text = response.text.strip()
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            clean_json = raw_text[start:end+1]
            try:
                result = json.loads(clean_json)
            except:
                clean_json = re.sub(r'(\w+):\s*"', r'"\1": "', clean_json)
                result = json.loads(clean_json, strict=False)
        else:
            raise ValueError("No JSON found")
        subject = result.get("subject", f"Application for {job.get('title')}")
        body = result.get("body", "I came across this role and believe my skills align well with your team.")

        # QC Pass
        qc_model = genai.GenerativeModel("models/gemini-flash-latest")
        qc_resp = qc_model.generate_content(f"Does this email start with a sentence about the candidate and avoid 'I am writing to'? Return JSON {{'passes':bool}}. \nEmail: {body}")
        if "false" in qc_resp.text.lower():
            logger.warning("[Email Drafter] QC failed.")
        
        return {
            "subject": subject,
            "body": body,
            "recommended_resume_path": resume.file_path
        }

    except Exception as e:
        logger.error(f"[Email Drafter] Failed to draft email: {e}")
        return {
            "subject": f"Application for {job.get('title')}",
            "body": "I am writing to apply for the position. Please see the attached resume.",
            "recommended_resume_path": resume.file_path
        }
