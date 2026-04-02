"""
backend/modules/ai_engine/resume_parser.py — AI-powered resume extractor.
"""
import json
import logging
import google.generativeai as genai
from backend.config import settings

logger = logging.getLogger(__name__)

VALID_ROLE_TYPES = ["frontend", "backend", "fullstack", "ai", "devops", "freelancer", "other"]

def parse_resume_content(text: str) -> dict:
    """Uses Gemini to extract skills, experience summary, and role type from raw resume text."""
    if not settings.gemini_api_key:
        logger.warning("No Gemini API key, skipping resume parsing.")
        return {"skills": [], "experience_summary": "AI parsing disabled.", "role_type": "other"}

    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""
        You are an expert technical recruiter analyzing a resume.
        Read the provided resume text and extract the core professional profile.
        
        Format your response EXACTLY as a valid JSON object with the following schema, and no other text:
        {{
            "role_type": "one of: {', '.join(VALID_ROLE_TYPES)} - choose the single best fit based on their experience.",
            "skills": ["list", "of", "top", "10", "hard", "skills", "like", "React", "Python", "AWS"],
            "experience_summary": "A punchy, 2-3 sentence summary of their years of experience, core competence, and domain expertise."
        }}

        If the text is empty or invalid, return an empty array for skills, "other" for role_type, and "No summary available."
        
        Resume Text:
        {text[:10000]}
        """
        
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        
        # Validation fallback
        if data.get("role_type") not in VALID_ROLE_TYPES:
            data["role_type"] = "other"
            
        return data
    except Exception as e:
        logger.error(f"Failed to parse resume with AI: {e}")
        return {"skills": [], "experience_summary": f"Extraction failed: {str(e)}", "role_type": "other"}
