"""
hackernews.py — Scrapes Hacker News "Who Is Hiring?" monthly thread.
Uses HN Algolia search API to find the current month's thread.
"""
import asyncio
import httpx
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

from backend.modules.scraper.base import BaseScraper
from backend.modules.scraper.normalizer import normalize
from backend.config import settings


class HackerNewsScraper(BaseScraper):
    source_name = "hackernews"
    priority = 5

    HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
    HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
    HN_PARENT_SEARCH = "https://hn.algolia.com/api/v1/search"

    async def _find_hiring_thread_id(self, client: httpx.AsyncClient) -> int | None:
        """Find the most recent 'Who is hiring?' thread ID."""
        resp = await client.get(
            self.HN_PARENT_SEARCH,
            params={
                "query": "Ask HN: Who is hiring?",
                "tags": "ask_hn",
                "hitsPerPage": 1,
            }
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if hits:
            return int(hits[0].get("objectID", 0))
        return None

    async def fetch_jobs(self) -> List[Dict[str, Any]]:
        result = []
        headers = {"User-Agent": settings.user_agent}

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            thread_id = await self._find_hiring_thread_id(client)
            if not thread_id:
                return []

            await asyncio.sleep(settings.scrape_delay)

            # Get all comments from the thread
            resp = await client.get(
                self.HN_SEARCH,
                params={
                    "tags": f"comment,story_{thread_id}",
                    "hitsPerPage": 500,
                }
            )
            resp.raise_for_status()
            comments = resp.json().get("hits", [])

            for comment in comments:
                text = comment.get("comment_text", "") or ""
                obj_id = comment.get("objectID", "")
                created_at_str = comment.get("created_at")

                # Skip if doesn't mention our keywords
                combined = text.lower()
                if not any(kw.lower() in combined for kw in self.keywords):
                    continue

                # Extract: first line usually has "Company | Location | Remote | ..."
                lines = [l.strip() for l in re.sub(r"<[^>]+>", "", text).split("\n") if l.strip()]
                first_line = lines[0] if lines else ""
                parts = [p.strip() for p in first_line.split("|")]

                title = "Software Engineer"  # HN comments don't always have structured titles
                company = parts[0] if parts else "Unknown"
                location = parts[1] if len(parts) > 1 else "See description"

                # Detect if remote
                if any(w in combined for w in ["remote", "wfh", "work from home"]):
                    location = "Remote"

                url = f"https://news.ycombinator.com/item?id={obj_id}"

                posted_at = None
                if created_at_str:
                    try:
                        posted_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                normalized = normalize(
                    source=self.source_name,
                    raw=comment,
                    title=title,
                    company=company,
                    url=url,
                    location=location,
                    description=re.sub(r"<[^>]+>", "", text),
                    posted_at=posted_at,
                    source_id=obj_id,
                    tags=["hackernews"],
                )
                result.append(normalized)
                await asyncio.sleep(0.05)

        return result
