import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

WAAS_API_URL = "https://www.workatastartup.com/api/jobs"

async def scrape_waas() -> List[Dict[str, Any]]:
    """
    Scrape WorkAtAStartup (YC) official API.
    Note: Highly structured but may need a session or simple headers.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            logger.info(f"[WAAS] Fetching jobs from {WAAS_API_URL}...")
            async with session.get(WAAS_API_URL) as response:
                if response.status != 200:
                    logger.warning(f"[WAAS] API returned {response.status}")
                    return []
                
                data = await response.json()
                # Assuming the structure is a list or contains a list of jobs
                # Adjust based on real API response
                jobs = data if isinstance(data, list) else data.get("jobs", [])
                
                results = []
                for job in jobs[:50]:
                    results.append({
                        "title": job.get("job_title", job.get("title", "Unknown Title")),
                        "company": job.get("company_name", job.get("company", "YC Startup")),
                        "description": job.get("job_description", job.get("description", "")),
                        "url": job.get("job_url", job.get("url", "https://www.workatastartup.com")),
                        "location": job.get("location", "Remote"),
                        "posted_at": datetime.now(timezone.utc),
                        "source": "workatastartup"
                    })
                
                logger.info(f"[WAAS] Found {len(results)} jobs.")
                return results
                
        except Exception as e:
            logger.error(f"[WAAS] Scraper failed: {e}")
            return []
