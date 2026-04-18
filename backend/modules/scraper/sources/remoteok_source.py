import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REMOTEOK_API_URL = "https://remoteok.com/api"

async def scrape_remoteok() -> List[Dict[str, Any]]:
    """
    Fetch jobs from RemoteOK Official API.
    Returns normalized job dicts.
    """
    logger.info(f"[RemoteOK] Fetching jobs via API...")
    
    headers = {
        "User-Agent": "JobAutomater/1.0 (Personal tool; global job search)"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(REMOTEOK_API_URL, headers=headers, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"[RemoteOK] API Error {response.status}")
                    return []
                
                data = await response.json()
                # RemoteOK API returns a list where the first item is an info object, not a job
                if not isinstance(data, list) or len(data) <= 1:
                    return []
                
                jobs = data[1:] # Skip the legal/info object
                
                normalized = []
                for j in jobs:
                    # RemoteOK date is an integer timestamp or ISO string depending on version
                    # but usually it's in epoch
                    posted_at = datetime.now(timezone.utc)
                    try:
                        ts = j.get("date")
                        if isinstance(ts, int):
                            posted_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                        elif isinstance(ts, str):
                            posted_at = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    except:
                        pass

                    job_url = j.get("url")
                    if not job_url:
                        continue

                    job_data = {
                        "title": j.get("position"),
                        "company": j.get("company"),
                        "location": j.get("location") or "Remote",
                        "description": j.get("description"),
                        "url": job_url,
                        "posted_at": posted_at,
                        "salary_min": j.get("salary_min"),
                        "salary_max": j.get("salary_max"),
                        "source": "remoteok",
                        "tags": j.get("tags", [])
                    }
                    normalized.append(job_data)
                
                logger.info(f"[RemoteOK] Found {len(normalized)} jobs")
                return normalized

    except Exception as e:
        logger.error(f"[RemoteOK] Failed: {e}")
        return []
