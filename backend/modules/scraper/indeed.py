"""
indeed.py — Scrapes Indeed RSS feeds by keyword + location.
Uses public RSS (no API key needed).
"""
import asyncio
import httpx
import feedparser
from datetime import datetime
from typing import List, Dict, Any
from email.utils import parsedate_to_datetime

from backend.modules.scraper.base import BaseScraper
from backend.modules.scraper.normalizer import normalize
from backend.config import settings


class IndeedScraper(BaseScraper):
    source_name = "indeed"
    priority = 4

    RSS_URL = "https://www.indeed.com/rss"

    async def _fetch_feed(self, client: httpx.AsyncClient, query: str, location: str) -> List[Dict]:
        """Fetch a single Indeed RSS feed."""
        params = {
            "q": query,
            "l": location,
            "sort": "date",
            "radius": "50",
            "fromage": "7",  # last 7 days
        }
        try:
            resp = await client.get(self.RSS_URL, params=params)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            return feed.entries
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Indeed feed failed for {query}/{location}: {e}")
            return []

    async def fetch_jobs(self) -> List[Dict[str, Any]]:
        result = []
        seen_urls = set()

        # Search combos: each keyword × locations
        locations = settings.preferred_locations_list

        headers = {
            "User-Agent": settings.user_agent,
        }

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            for keyword in self.keywords[:5]:  # limit to top 5 keywords
                for location in locations:
                    await asyncio.sleep(settings.scrape_delay)
                    entries = await self._fetch_feed(client, keyword, location)

                    for entry in entries:
                        url = entry.get("link", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        title = entry.get("title", "")
                        desc = entry.get("summary", "")
                        source_id = entry.get("id", url)

                        # Extract company from title if formatted "Title - Company"
                        company = ""
                        if " - " in title:
                            parts = title.rsplit(" - ", 1)
                            title = parts[0].strip()
                            company = parts[1].strip()

                        posted_at = None
                        published = entry.get("published")
                        if published:
                            try:
                                posted_at = parsedate_to_datetime(published)
                            except Exception:
                                pass

                        loc_tag = location if location else "Various"
                        normalized = normalize(
                            source=self.source_name,
                            raw=dict(entry),
                            title=title,
                            company=company,
                            url=url,
                            location=loc_tag,
                            description=desc,
                            posted_at=posted_at,
                            source_id=source_id,
                            tags=[keyword.lower(), location.lower() or "worldwide"],
                        )
                        result.append(normalized)

        return result
