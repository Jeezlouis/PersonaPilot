import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone
from backend.config import settings

logger = logging.getLogger(__name__)

# Adzuna API endpoint: https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
ADZUNA_API_URL = "https://api.adzuna.com/v1/api/jobs/gb/search/1" # defaulting to UK for remote or globally

async def scrape_adzuna(keywords: List[str] = []) -> List[Dict[str, Any]]:
    """
    Scrape jobs from Adzuna API.
    Requires app_id and app_key.
    """
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        logger.warning("[Adzuna] Missing API credentials. Skipping.")
        return []

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    
    query = keywords[0] if keywords else "Software Engineer"
    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "results_per_page": 50,
        "what": query,
        "content-type": "application/json"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            logger.info(f"[Adzuna] Fetching jobs for query: {query}...")
            async with session.get(ADZUNA_API_URL, params=params) as response:
                if response.status != 200:
                    logger.warning(f"[Adzuna] API status {response.status}")
                    return []
                
                data = await response.json()
                results = []
                for job in data.get("results", []):
                    results.append({
                        "title": job.get("title", ""),
                        "company": job.get("company", {}).get("display_name", "Unknown"),
                        "description": job.get("description", ""),
                        "url": job.get("redirect_url", ""),
                        "location": job.get("location", {}).get("display_name", "Remote"),
                        "posted_at": datetime.now(timezone.utc),
                        "salary_min": job.get("salary_min"),
                        "salary_max": job.get("salary_max"),
                        "source": "adzuna"
                    })
                
                logger.info(f"[Adzuna] Found {len(results)} jobs.")
                return results
                
        except Exception as e:
            logger.error(f"[Adzuna] Scraper failed: {e}")
            return []
