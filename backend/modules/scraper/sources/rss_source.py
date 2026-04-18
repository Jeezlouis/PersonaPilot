"""
RSS Feed Scraper — high reliability source for remote-friendly job boards.
Uses feedparser for RemoteOK, WWR, and YC feeds.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
import time

try:
    import feedparser
except ImportError:
    feedparser = None

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
]

async def scrape_rss_feeds() -> List[Dict[str, Any]]:
    """
    Scrape all configured RSS feeds.
    Returns normalized job dicts.
    """
    if not feedparser:
        logger.error("feedparser not installed. Please run 'pip install feedparser'.")
        return []

    all_jobs = []
    
    for feed_url in RSS_FEEDS:
        try:
            logger.info(f"[RSS] Scraping feed: {feed_url}...")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    # Generic RSS mapping
                    title = getattr(entry, "title", "No Title")
                    company = ""
                    if " @ " in title:
                        title, company = title.split(" @ ", 1)
                    elif " - " in title:
                        title, company = title.split(" - ", 1)
                    
                    url = getattr(entry, "link", "")
                    description = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    
                    # Try to parse published date
                    published = None
                    if hasattr(entry, "published_parsed"):
                        published = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                    elif hasattr(entry, "updated_parsed"):
                        published = datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
                    else:
                        published = datetime.now(timezone.utc)
                        
                    all_jobs.append({
                        "title": title.strip(),
                        "company": company.strip() if company else "the hiring team",
                        "location": "Remote",
                        "description": description,
                        "url": url,
                        "posted_at": published,
                        "source": f"rss_{_get_domain(feed_url)}",
                    })
                except Exception as e:
                    logger.debug(f"[RSS] Failed to parse entry in {feed_url}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"[RSS] Failed to scrape feed {feed_url}: {e}")
            continue
            
    return all_jobs

def _get_domain(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "").split(".")[0]
