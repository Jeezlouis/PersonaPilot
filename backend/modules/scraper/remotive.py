"""
remotive.py — Scrapes Remotive.com public API.
Excellent remote job board with clean JSON.
"""
import asyncio
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any
from dateutil import parser as dateparser

from backend.modules.scraper.base import BaseScraper
from backend.modules.scraper.normalizer import normalize
from backend.config import settings


CATEGORY_MAP = {
    "software-dev": "Software Engineer,Backend Developer,Full Stack Developer,Frontend Developer",
    "design": "Frontend Developer",
    "devops-sysadmin": "DevOps",
    "data": "AI Engineer,Data Scientist",
    "product": "Product Manager",
}


class RemotiveScraper(BaseScraper):
    source_name = "remotive"
    priority = 2
    supports_remote_filter = True

    BASE_URL = "https://remotive.com/api/remote-jobs"

    async def fetch_jobs(self) -> List[Dict[str, Any]]:
        result = []
        headers = {"User-Agent": settings.user_agent}

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            for category in ["software-dev", "data"]:
                await asyncio.sleep(settings.scrape_delay)
                try:
                    resp = await client.get(
                        self.BASE_URL,
                        params={"category": category, "limit": 100}
                    )
                    resp.raise_for_status()
                    jobs_raw = resp.json().get("jobs", [])
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Remotive category {category} failed: {e}")
                    continue

                for job in jobs_raw:
                    title = job.get("title", "")
                    company = job.get("company_name", "")
                    url = job.get("url", "")
                    desc = job.get("description", "")
                    tags = job.get("tags", [])
                    source_id = str(job.get("id", ""))

                    combined = f"{title} {' '.join(tags)} {desc}".lower()
                    if not any(kw.lower() in combined for kw in self.keywords):
                        continue

                    posted_str = job.get("publication_date")
                    try:
                        posted_at = dateparser.parse(posted_str) if posted_str else None
                    except Exception:
                        posted_at = None

                    normalized = normalize(
                        source=self.source_name,
                        raw=job,
                        title=title,
                        company=company,
                        url=url,
                        location="Remote",
                        description=desc,
                        posted_at=posted_at,
                        source_id=source_id,
                        tags=tags,
                    )
                    normalized["job_type"] = "remote"
                    result.append(normalized)

        return result
