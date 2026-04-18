import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone
from backend.config import settings

logger = logging.getLogger(__name__)

# Jooble API endpoint: https://jooble.org/api/{api_key}
JOOBLE_API_URL = "https://jooble.org/api/"

async def scrape_jooble(keywords: List[str] = []) -> List[Dict[str, Any]]:
    """
    Search jobs from Jooble API.
    Requires api_key.
    """
    if not settings.jooble_api_key:
        logger.warning("[Jooble] Missing API key. Skipping.")
        return []

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }
    
    query = keywords[0] if keywords else "Software Engineer"
    payload = {
        "keywords": query,
        "location": "remote"
    }
    
    url = f"{JOOBLE_API_URL}{settings.jooble_api_key}"
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            logger.info(f"[Jooble] Searching for query: {query}...")
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    logger.warning(f"[Jooble] API status {response.status}")
                    return []
                
                data = await response.json()
                results = []
                for job in data.get("jobs", []):
                    results.append({
                        "title": job.get("title", ""),
                        "company": job.get("company", "Unknown"),
                        "description": job.get("snippet", ""),
                        "url": job.get("link", ""),
                        "location": job.get("location", "Remote"),
                        "posted_at": datetime.now(timezone.utc),
                        "source": "jooble"
                    })
                
                logger.info(f"[Jooble] Found {len(results)} jobs.")
                return results
                
        except Exception as e:
            logger.error(f"[Jooble] Scraper failed: {e}")
            return []
