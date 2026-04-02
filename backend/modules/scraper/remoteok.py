"""
remoteok.py — Scrapes RemoteOK public JSON API.
No auth required. Rate-limit: be polite.
"""
import asyncio
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any

from backend.modules.scraper.base import BaseScraper
from backend.modules.scraper.normalizer import normalize
from backend.config import settings


class RemoteOKScraper(BaseScraper):
    source_name = "remoteok"
    priority = 1
    supports_remote_filter = True

    BASE_URL = "https://remoteok.com/api"

    async def fetch_jobs(self) -> List[Dict[str, Any]]:
        headers = {
            "User-Agent": settings.user_agent,
            "Accept": "application/json",
        }
        result = []

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            response = await client.get(self.BASE_URL)
            response.raise_for_status()
            data = response.json()

        # First item is a legal notice object, skip it
        jobs_raw = [item for item in data if item.get("slug")]

        for job in jobs_raw:
            title = job.get("position", "")
            company = job.get("company", "")
            tags = job.get("tags", [])
            url = job.get("url", f"https://remoteok.com/remote-jobs/{job.get('slug', '')}")
            desc = job.get("description", "")
            source_id = str(job.get("id", ""))

            # Filter by keywords
            combined = f"{title} {' '.join(tags)} {desc}".lower()
            if not any(kw.lower() in combined for kw in self.keywords):
                continue

            # Parse posted_at
            epoch = job.get("epoch")
            posted_at = datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else None

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
            # RemoteOK is always remote
            normalized["job_type"] = "remote"
            result.append(normalized)

            await asyncio.sleep(0.1)  # gentle pacing

        return result
