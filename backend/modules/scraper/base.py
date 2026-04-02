"""
base.py — Abstract base class for all scrapers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    source_name: str = "unknown"
    priority: int = 5  # 1=highest, 10=lowest
    supports_remote_filter: bool = False

    def __init__(self, keywords: List[str], prefer_remote: bool = True):
        self.keywords = keywords
        self.prefer_remote = prefer_remote

    @abstractmethod
    async def fetch_jobs(self) -> List[Dict[str, Any]]:
        """
        Fetch raw jobs from the source.
        Returns a list of normalized job dicts (using normalizer.normalize).
        """
        pass

    async def run(self) -> List[Dict[str, Any]]:
        """Entry point. Wraps fetch_jobs with error handling."""
        try:
            logger.info(f"[{self.source_name}] Starting scrape...")
            jobs = await self.fetch_jobs()
            logger.info(f"[{self.source_name}] Found {len(jobs)} jobs.")
            return jobs
        except Exception as e:
            logger.error(f"[{self.source_name}] Scrape failed: {e}", exc_info=True)
            return []
