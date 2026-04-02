"""
weworkremotely.py — Scrapes We Work Remotely RSS feeds.
Reliable, no auth needed.
"""
import asyncio
import httpx
import feedparser
from datetime import datetime, timezone
from typing import List, Dict, Any
from email.utils import parsedate_to_datetime

from backend.modules.scraper.base import BaseScraper
from backend.modules.scraper.normalizer import normalize
from backend.config import settings


WWR_FEEDS = [
    ("https://weworkremotely.com/categories/remote-programming-jobs.rss", ["programming"]),
    ("https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss", ["fullstack"]),
    ("https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss", ["frontend"]),
    ("https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss", ["backend"]),
]


class WeWorkRemotelyScraper(BaseScraper):
    source_name = "weworkremotely"
    priority = 3
    supports_remote_filter = True

    async def fetch_jobs(self) -> List[Dict[str, Any]]:
        result = []
        headers = {"User-Agent": settings.user_agent}

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            for feed_url, feed_tags in WWR_FEEDS:
                await asyncio.sleep(settings.scrape_delay)
                try:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"WWR feed {feed_url} failed: {e}")
                    continue

                for entry in feed.entries:
                    title = entry.get("title", "")
                    # WWR titles are like "Company: Job Title"
                    if ": " in title:
                        company, title = title.split(": ", 1)
                    else:
                        company = ""

                    url = entry.get("link", "")
                    desc = entry.get("summary", "")
                    source_id = entry.get("id", url)

                    combined = f"{title} {desc}".lower()
                    if not any(kw.lower() in combined for kw in self.keywords):
                        continue

                    # Parse date
                    posted_at = None
                    published = entry.get("published")
                    if published:
                        try:
                            posted_at = parsedate_to_datetime(published)
                        except Exception:
                            pass

                    normalized = normalize(
                        source=self.source_name,
                        raw=dict(entry),
                        title=title,
                        company=company,
                        url=url,
                        location="Remote",
                        description=desc,
                        posted_at=posted_at,
                        source_id=source_id,
                        tags=feed_tags,
                    )
                    normalized["job_type"] = "remote"
                    result.append(normalized)

        return result
