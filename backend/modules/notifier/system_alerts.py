"""
system_alerts.py — Proactive health alerts for the Job Automater.
Notifies via Telegram when the system detects anomalies.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from backend.database import AsyncSessionLocal
from backend.models import ScrapeRun, PendingJob
from backend.modules.notifier.telegram import notify_error

logger = logging.getLogger(__name__)

async def check_system_health():
    """
    Check for common failure patterns and alert if found.
    1. Zero results in last 3 scrape runs.
    2. Queue backlog > 50 jobs.
    3. High failure rate in worker.
    """
    async with AsyncSessionLocal() as db:
        from backend.models import SchedulerRun
        # 1. Check for consecutive zero-result scrapes
        recent_runs = await db.execute(
            select(SchedulerRun)
            .where(SchedulerRun.task_name == "job_scraper")
            .order_by(SchedulerRun.started_at.desc())
            .limit(3)
        )
        runs = recent_runs.scalars().all()
        if len(runs) >= 3 and all(r.jobs_found == 0 for r in runs):
            await notify_error("Scraper Alert", "Zero jobs found in last 3 scrape runs. Check if selectors are broken.")

        # 2. Check Queue Backlog (Pending + Processing)
        backlog_count = await db.scalar(
            select(func.count(PendingJob.id))
            .where(PendingJob.status.in_(["pending", "processing"]))
        )
        if backlog_count > 50:
            await notify_error("Queue Alert", f"Large processing backlog: {backlog_count} jobs pending. Check worker logs.")

        # 3. Check Worker Failures (Last hour)
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        failed_count = await db.scalar(
            select(func.count(PendingJob.id))
            .where(PendingJob.status == "failed", PendingJob.queued_at >= hour_ago)
        )
        if failed_count > 5:
            await notify_error("Worker Alert", f"High failure rate: {failed_count} jobs failed in the last hour.")
