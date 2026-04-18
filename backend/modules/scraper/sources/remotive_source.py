import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"

async def scrape_remotive(category: str = None) -> List[Dict[str, Any]]:
    """
    Fetch jobs from Remotive API.
    """
    logger.info(f"[Remotive] Fetching jobs...")
    params = {}
    if category:
        params["category"] = category

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(REMOTIVE_API_URL, params=params, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"[Remotive] Error {response.status}")
                    return []
                
                data = await response.json()
                jobs = data.get("jobs", [])
                
                normalized = []
                for j in jobs:
                    # Parse date: e.g. "2024-04-14T12:00:00"
                    posted_at = datetime.now(timezone.utc)
                    try:
                        date_str = j.get("publication_date")
                        if date_str:
                            posted_at = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                    except:
                        pass

                    job_url = j.get("url")
                    if not job_url:
                        continue

                    normalized.append({
                        "title": j.get("title"),
                        "company": j.get("company_name"),
                        "location": j.get("candidate_required_location", "Remote"),
                        "description": j.get("description"),
                        "url": job_url,
                        "posted_at": posted_at,
                        "salary_min": j.get("salary") if isinstance(j.get("salary"), (int, float)) else None, # Remotive salary is usually a string, skip for now
                        "source": "remotive",
                        "job_type": "remote"
                    })
                
                logger.info(f"[Remotive] Found {len(normalized)} jobs")
                return normalized

    except Exception as e:
        logger.error(f"[Remotive] Failed: {e}")
        return []
