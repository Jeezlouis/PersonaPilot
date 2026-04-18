"""
__init__.py — Scraper module registry.
"""
from backend.modules.scraper.remoteok import RemoteOKScraper
from backend.modules.scraper.remotive import RemotiveScraper
from backend.modules.scraper.weworkremotely import WeWorkRemotelyScraper
from backend.modules.scraper.hackernews import HackerNewsScraper

ALL_SCRAPERS = [
    RemoteOKScraper,
    RemotiveScraper,
    WeWorkRemotelyScraper,
    HackerNewsScraper,
]
