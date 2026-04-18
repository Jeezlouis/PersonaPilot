
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from backend.database import AsyncSessionLocal
from backend.models import Job
from backend.modules.scorer.scorer import score_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reproccessor")

async def reprocess_today_skipped():
    async with AsyncSessionLocal() as db:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        
        # Get skipped jobs from today
        result = await db.execute(
            select(Job).where(Job.status == "skipped", Job.found_at >= today_start)
        )
        skipped_jobs = result.scalars().all()
        
        logger.info(f"Found {len(skipped_jobs)} skipped jobs from today. Attempting to re-score...")
        
        recovered_count = 0
        for job in skipped_jobs:
            # Prepare data for scorer
            job_data = {
                "title": job.title,
                "description": job.description,
                "role_category": job.role_category,
                "posted_at": job.posted_at,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "hash_id": job.hash_id
            }
            
            # Re-score with new logic
            new_score = await score_job(job_data, db)
            
            # If it now passes (or is at least marked new)
            if new_score >= 60: # Using default threshold from .env
                logger.info(f"🏆 RECOVERED: '{job.title}' (Score: {new_score})")
                job.match_score = new_score
                job.status = "new"
                recovered_count += 1
            else:
                job.match_score = new_score # Update score anyway
                
        await db.commit()
        logger.info(f"Reprocessing complete. Recovered {recovered_count} jobs.")

if __name__ == "__main__":
    asyncio.run(reprocess_today_skipped())
