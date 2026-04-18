import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

HIMALAYAS_API_URL = "https://himalayas.app/api/jobs"

async def scrape_himalayas() -> List[Dict[str, Any]]:
    """
    Fetch jobs from Himalayas Official API.
    """
    logger.info(f"[Himalayas] Fetching jobs via API...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HIMALAYAS_API_URL, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"[Himalayas] API Error {response.status}")
                    return []
                
                data = await response.json()
                jobs = data.get("jobs", [])
                
                normalized = []
                for j in jobs:
                    posted_at = datetime.now(timezone.utc)
                    try:
                        # Himalayas uses unix timestamp
                        ts = j.get("pub_date")
                        if ts:
                            posted_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                    except:
                        pass

                    job_url = j.get("url")
                    if not job_url:
                        continue

                    normalized.append({
                        "title": j.get("title"),
                        "company": j.get("company_name"),
                        "location": j.get("location") or "Remote",
                        "description": j.get("description"),
                        "url": job_url,
                        "posted_at": posted_at,
                        "salary_min": j.get("salary_min"),
                        "salary_max": j.get("salary_max"),
                        "source": "himalayas",
                        "tags": j.get("categories", [])
                    })
                
                logger.info(f"[Himalayas) Found {len(normalized)} jobs")
                return normalized

    except Exception as e:
        logger.error(f"[Himalayas] Failed: {e}")
        return []
