import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone
import re

logger = logging.getLogger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"

async def scrape_hacker_news() -> List[Dict[str, Any]]:
    """
    Fetch 'Who is Hiring' posts from Hacker News via Algolia API.
    Extracts individual job entries from comments.
    """
    logger.info(f"[HN] Fetching latest 'Who is Hiring' thread...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Get the latest 'Who is Hiring' story ID
            params = {
                "tags": "story,author_whoishiring",
                "hitsPerPage": 1
            }
            async with session.get(HN_SEARCH_URL, params=params) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                hits = data.get("hits", [])
                if not hits:
                    return []
                
                story_id = hits[0].get("objectID")
                story_title = hits[0].get("title")
                logger.info(f"[HN] Found thread: {story_title} (ID: {story_id})")

            # 2. Get comments for this story
            # Algolia 'search' allows filtering by parent_id
            params = {
                "tags": f"comment,story_{story_id}",
                "hitsPerPage": 1000 # HN threads can be large
            }
            async with session.get(HN_SEARCH_URL, params=params) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                comments = data.get("hits", [])
                
                jobs = []
                for c in comments:
                    text = c.get("comment_text", "")
                    if not text:
                        continue
                        
                    # Basic parser for HN 'Who is Hiring' format
                    # Format is usually: COMPANY | ROLE | LOCATION | REMOTE/ONSITE | SALARY (optional)
                    # We look for lines containing '|'
                    lines = text.split("<p>")
                    header = lines[0]
                    
                    if "|" in header:
                        parts = [p.strip() for p in header.split("|")]
                        if len(parts) >= 2:
                            company = parts[0]
                            title = parts[1]
                            location = parts[2] if len(parts) > 2 else "Remote"
                            
                            jobs.append({
                                "title": _clean_html(title),
                                "company": _clean_html(company),
                                "location": _clean_html(location),
                                "description": _clean_html(text),
                                "url": f"https://news.ycombinator.com/item?id={c.get('objectID')}",
                                "posted_at": datetime.fromtimestamp(c.get("created_at"), tz=timezone.utc),
                                "source": "hacker_news",
                            })
                
                logger.info(f"[HN] Extracted {len(jobs)} jobs from thread")
                return jobs

    except Exception as e:
        logger.error(f"[HN] Failed: {e}")
        return []

def _clean_html(text: str) -> str:
    # Basic HTML tag removal
    clean = re.sub(r'<.*?>', '', text)
    return clean.strip()
