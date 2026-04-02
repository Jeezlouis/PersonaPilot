"""
normalizer.py — Converts raw job data from any source into
a unified JobSchema dict ready for DB insertion.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any


ROLE_KEYWORDS = {
    "frontend": [
        "react", "vue", "angular", "next.js", "nuxt", "svelte", "css",
        "html", "ui", "ux", "tailwind", "sass", "frontend", "front-end",
        "javascript", "typescript", "webpack", "vite", "figma",
    ],
    "backend": [
        "node", "fastapi", "django", "flask", "spring", "rails", "laravel",
        "express", "rest api", "graphql", "postgresql", "mysql", "mongodb",
        "redis", "kafka", "microservices", "backend", "back-end", "server",
        "python", "java", "go", "rust", "kotlin", "php",
    ],
    "fullstack": [
        "full stack", "fullstack", "full-stack", "mern", "mean", "lamp",
        "t3 stack", "both frontend and backend",
    ],
    "ai": [
        "machine learning", "deep learning", "llm", "gpt", "ai", "ml",
        "nlp", "computer vision", "langchain", "openai", "huggingface",
        "tensorflow", "pytorch", "data science", "automation", "rag",
    ],
    "devops": [
        "devops", "kubernetes", "docker", "ci/cd", "terraform", "aws",
        "gcp", "azure", "infrastructure", "sre", "cloud", "ansible",
    ],
}

EMPLOYMENT_KEYWORDS = {
    "freelance": ["freelance", "contract", "gig", "upwork", "fiverr", "hourly"],
    "part-time": ["part-time", "part time", "parttime"],
    "full-time": ["full-time", "full time", "fulltime", "permanent"],
    "internship": ["intern", "internship"],
}

JOB_TYPE_KEYWORDS = {
    "remote": ["remote", "work from home", "wfh", "distributed", "anywhere"],
    "hybrid": ["hybrid"],
    "onsite": ["on-site", "onsite", "in-office", "office", "in person"],
}


def detect_role_category(text: str) -> str:
    """Detect the role category from job text."""
    text_lower = text.lower()
    scores = {cat: 0 for cat in ROLE_KEYWORDS}
    for cat, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[cat] += 1
    # Fullstack gets a bonus if both frontend and backend score
    if scores["frontend"] >= 2 and scores["backend"] >= 2:
        scores["fullstack"] += 3
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


def detect_employment_type(text: str) -> str:
    text_lower = text.lower()
    for emp_type, keywords in EMPLOYMENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return emp_type
    return "full-time"


def detect_job_type(location: str, text: str) -> str:
    combined = f"{location or ''} {text or ''}".lower()
    for job_type, keywords in JOB_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return job_type
    return "onsite"


def extract_salary(text: str) -> tuple[Optional[float], Optional[float]]:
    """Extract salary range from text. Returns (min, max) in USD annual."""
    if not text:
        return None, None
    # Patterns like $80k-$120k, $80,000 - $120,000, 80000-120000
    patterns = [
        r"\$(\d+)k?\s*[-–]\s*\$(\d+)k?",
        r"(\d{2,3}),?000\s*[-–]\s*(\d{2,3}),?000",
        r"(\d+)k\s*[-–]\s*(\d+)k",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            lo, hi = float(match.group(1)), float(match.group(2))
            # Convert k to full number
            if lo < 1000:
                lo *= 1000
            if hi < 1000:
                hi *= 1000
            return lo, hi
    return None, None


def compute_hash(url: str, title: str, company: Optional[str]) -> str:
    """Generate a unique dedup hash for a job."""
    raw = f"{url}|{title.lower().strip()}|{(company or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def normalize(
    source: str,
    raw: Dict[str, Any],
    title: str,
    company: Optional[str],
    url: str,
    location: Optional[str] = None,
    description: Optional[str] = None,
    posted_at: Optional[datetime] = None,
    source_id: Optional[str] = None,
    tags: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Normalize a raw job into the common schema dict.
    Returns a dict matching the Job model columns.
    """
    desc_full = f"{title} {company or ''} {description or ''}".strip()

    salary_min, salary_max = extract_salary(description or "")
    role_category = detect_role_category(desc_full)
    employment_type = detect_employment_type(desc_full)
    job_type = detect_job_type(location or "", desc_full)

    # Prioritize remote tagging
    if job_type == "remote":
        job_type = "remote"

    return {
        "source": source,
        "source_id": source_id,
        "url": url,
        "title": title,
        "company": company,
        "location": location or "Not specified",
        "job_type": job_type,
        "employment_type": employment_type,
        "role_category": role_category,
        "description": description,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "posted_at": posted_at,
        "found_at": datetime.now(timezone.utc),
        "status": "new",
        "match_score": 0.0,
        "hash_id": compute_hash(url, title, company),
        "tags": tags or [],
        "raw_data": raw,
    }
