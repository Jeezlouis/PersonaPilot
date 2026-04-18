import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

JOBICY_API_URL = "https://jobicy.com/api/v2/remote-jobs"

async def scrape_jobicy(count: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch jobs from Jobicy Official API.
    """
    logger.info(f"[Jobicy] Fetching jobs via API...")
    
    params = {
        "count": count
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(JOBICY_API_URL, params=params, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"[Jobicy] API Error {response.status}")
                    return []
                
                data = await response.json()
                jobs = data.get("jobs", [])
                
                normalized = []
                for j in jobs:
                    posted_at = datetime.now(timezone.utc)
                    try:
                        date_str = j.get("pubDate")
                        if date_str:
                            # Jobicy format: "2024-04-14 12:00:00"
                            posted_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    except:
                        pass

                    normalized.append({
                        "title": j.get("jobTitle"),
                        "company": j.get("companyName"),
                        "location": j.get("jobGeo", "Remote"),
                        "description": j.get("jobDescription"),
                        "url": j.get("url"),
                        "posted_at": posted_at,
                        "salary_min": None,
                        "salary_max": None,
                        "source": "jobicy",
                        "tags": j.get("jobIndustry", [])
                    })
                
                logger.info(f"[Jobicy] Found {len(normalized)} jobs")
                return normalized

    except Exception as e:
        logger.error(f"[Jobicy] Failed: {e}")
        return []
