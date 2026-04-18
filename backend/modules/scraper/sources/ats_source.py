import logging
import aiohttp
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ATS generic scraper for specific company IDs (remote pioneers)
# Example companies: Deel, Remote, Oyster, Gitlab, Hopin, Toptal
REMOTE_FIRST_COMPANIES = ["deel", "remote", "oyster", "gitlab", "hopin", "toptal"]

async def scrape_ats_endpoints(company_ids: List[str] = REMOTE_FIRST_COMPANIES) -> List[Dict[str, Any]]:
    """
    Scrape Greenhouse and Lever endpoints for specific remote-first companies.
    """
    all_jobs = []
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        for company in company_ids:
            # Try Lever first (JSON API)
            lever_url = f"https://api.lever.co/v0/postings/{company}?mode=json"
            try:
                logger.info(f"[ATS] Checking Lever for {company}...")
                async with session.get(lever_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for job in data:
                            all_jobs.append({
                                "title": job.get("text", ""),
                                "company": company.capitalize(),
                                "description": job.get("descriptionPlain", ""),
                                "url": job.get("hostedUrl", ""),
                                "location": job.get("categories", {}).get("location", "Remote"),
                                "posted_at": datetime.now(timezone.utc),
                                "source": "lever"
                            })
            except Exception as e:
                logger.debug(f"[ATS] Lever {company} failed: {e}")

            # Try Greenhouse (JSON API)
            # URL format: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
            gh_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
            try:
                logger.info(f"[ATS] Checking Greenhouse for {company}...")
                async with session.get(gh_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for job in data.get("jobs", []):
                            all_jobs.append({
                                "title": job.get("title", ""),
                                "company": company.capitalize(),
                                "description": "See Greenhouse for details",
                                "url": job.get("absolute_url", ""),
                                "location": job.get("location", {}).get("name", "Remote"),
                                "posted_at": datetime.now(timezone.utc),
                                "source": "greenhouse"
                            })
            except Exception as e:
                logger.debug(f"[ATS] Greenhouse {company} failed: {e}")

    logger.info(f"[ATS] Found total of {len(all_jobs)} jobs across {len(company_ids)} companies.")
    return all_jobs
