
import asyncio
import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Mocking the context for the failing job
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def test_generation():
    print("Starting AI Generation Test...")
    
    # This is roughly what the prompt looks like in the code
    resume_name = "Isreal"
    skills = "Python, FastAPI, Django, PostgreSQL, Git, Docker, AWS, React, Nginx, Redis"
    summary = "Versatile software engineer with experience in backend and frontend development."
    
    job_title = "Technical Support Specialist"
    company = "RSS Source"
    description = "We are looking for a technical support specialist to help our customers with technical issues."
    
    prompt = f"""You are writing a cover letter on behalf of {resume_name}, a versatile mid-level software engineer based in Nigeria...
    
CANDIDATE PROFILE:
{summary}

JOB DETAILS:
- Company: {company}
- Role: {job_title}
- Description: {description}
"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        print(f"Calling Gemini with model: {model.model_name}")
        response = await model.generate_content_async(prompt)
        print("--- AI RESPONSE ---")
        print(response.text)
        print("-------------------")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_generation())
