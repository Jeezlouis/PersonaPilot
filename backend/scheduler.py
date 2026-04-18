"""
scheduler.py — APScheduler-based task scheduler.
Runs scraping, scoring, notifications, and follow-up checks.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, func, update

from backend.database import AsyncSessionLocal
from backend.models import Job, Application, SchedulerRun, PendingJob, ScrapeRun
from backend.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


# ─── Task: Full Scrape Pipeline ───────────────────────────────────────────────
# ─── Task: Producer (Scraping & Queuing) ──────────────────────────────────────
async def run_job_scraper():
    """Producer: scrape → queue to pending_jobs."""
    task_name = "job_scraper"
    logger.info(f"[Scheduler] Starting {task_name}")
    
    async with AsyncSessionLocal() as db:
        # Phase 6 Visibility: Create record and commit immediately so it's visible in Health UI
        run = SchedulerRun(task_name=task_name, status="running")
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

        try:
            from backend.modules.scraper.sources.remotive_source import scrape_remotive
            from backend.modules.scraper.sources.rss_source import scrape_rss_feeds
            from backend.modules.scraper.sources.remoteok_source import scrape_remoteok
            from backend.modules.scraper.sources.jobicy_source import scrape_jobicy
            from backend.modules.scraper.sources.himalayas_source import scrape_himalayas
            from backend.modules.scraper.sources.hn_source import scrape_hacker_news
            from backend.modules.scraper.sources.adzuna_source import scrape_adzuna
            from backend.modules.scraper.sources.jooble_source import scrape_jooble
            from backend.modules.scraper.sources.waas_source import scrape_waas
            from backend.modules.scraper.sources.ats_source import scrape_ats_endpoints
            
            keywords = settings.search_keywords_list
            scrape_mode = settings.scrape_mode.lower()
            all_jobs = []

            # 🛠 HIGH PRIORITY: Global/Remote-First API Sources
            # 1. Remotive API
            all_jobs.extend(await scrape_remotive())
            # 2. RemoteOK API
            all_jobs.extend(await scrape_remoteok())
            # 3. Jobicy API
            all_jobs.extend(await scrape_jobicy())
            # 4. Himalayas API
            all_jobs.extend(await scrape_himalayas())
            # 5. Adzuna API (Requires key)
            all_jobs.extend(await scrape_adzuna(keywords))
            # 6. Jooble API (Requires key)
            all_jobs.extend(await scrape_jooble(keywords))
            # 7. WorkAtAStartup (YC API)
            all_jobs.extend(await scrape_waas())

            # 🛠 ATS DIRECT (Very Important - Never block)
            # Checking major remote companies direct Greenhouse/Lever
            all_jobs.extend(await scrape_ats_endpoints())

            # 🛠 MEDIUM PRIORITY: RSS Stack (Only high quality feeds)
            # Just WWR for now
            all_jobs.extend(await scrape_rss_feeds())
            
            logger.info(f"[Scraper] Stack found {len(all_jobs)} jobs across all sources")

            # 🛠 OPTIONAL/LOW PRIORITY: Hacker News
            # 1st of month only in prod, or anytime in local
            if datetime.now().day == 1 or scrape_mode == "local":
                 hn_jobs = await scrape_hacker_news()
                 all_jobs.extend(hn_jobs)
                 logger.info(f"[Scraper] Added {len(hn_jobs)} Hacker News jobs")

            # Queue all found jobs to pending_jobs
            # Wrap in ScrapeRun for Phase 6 visibility
            if all_jobs:
                import math
                from datetime import date
                def _sanitize_for_json(obj):
                    if obj is None:
                        return None
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    if isinstance(obj, dict):
                        return {k: _sanitize_for_json(v) for k, v in obj.items()}
                    if isinstance(obj, list):
                        return [_sanitize_for_json(v) for v in obj]
                    
                    # Handle NaN / Infinity (not valid in strict JSON)
                    if isinstance(obj, float):
                        if math.isnan(obj) or math.isinf(obj):
                            return None
                        return obj
                        
                    # Handle numpy types (common in pandas-based scrapers like JobSpy)
                    try:
                        # Check by class name to avoid hard dependency on numpy
                        cls_name = obj.__class__.__name__
                        if "int" in cls_name.lower() or "float" in cls_name.lower():
                            # Convert to standard python type
                            fval = float(obj)
                            if math.isnan(fval) or math.isinf(fval):
                                return None
                            return fval
                    except:
                        pass
                        
                    return obj

                for job_data in all_jobs:
                    safe_data = _sanitize_for_json(job_data)
                    pending = PendingJob(
                        raw_data=safe_data,
                        source=safe_data.get("source", "unknown"),
                    )
                    db.add(pending)
            
            await db.commit()
            logger.info(f"Queued {len(all_jobs)} jobs to pending_jobs.")

            # Update run record
            await db.execute(
                update(SchedulerRun)
                .where(SchedulerRun.id == run_id)
                .values(
                    status="success",
                    completed_at=datetime.now(timezone.utc),
                    jobs_found=len(all_jobs),
                    jobs_new=len(all_jobs),
                )
            )
            await db.commit()

        except Exception as e:
            logger.error(f"[Scheduler] {task_name} failed: {e}", exc_info=True)
            await db.execute(
                update(SchedulerRun)
                .where(SchedulerRun.id == run_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    errors=str(e),
                )
            )
            await db.commit()


# ─── Task: Consumer (AI Processing Worker) ────────────────────────────────────
async def run_processor_worker():
    """Consumer: process pending_jobs → dedup → classify → score → save."""
    from backend.modules.processor.worker import process_pending_jobs
    logger.debug("[Scheduler] Triggering processor worker...")
    await process_pending_jobs()


async def run_scrape_and_score():
    """Manually triggered task that runs both scraping and processing."""
    logger.info("[Scheduler] Manual trigger: run_scrape_and_score")
    await run_job_scraper()
    await run_processor_worker()


# ─── Task: System Health Check ────────────────────────────────────────────────
async def run_health_check():
    """Monitor for failures and send alerts."""
    from backend.modules.notifier.system_alerts import check_system_health
    await check_system_health()


# ─── Task: Daily Digest ───────────────────────────────────────────────────────
async def send_daily_digest():
    """Send morning summary via Telegram."""
    async with AsyncSessionLocal() as db:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

        new_today = await db.scalar(
            select(func.count(Job.id)).where(Job.found_at >= today_start)
        )
        high_match = await db.scalar(
            select(func.count(Job.id)).where(
                Job.found_at >= today_start,
                Job.match_score >= 80
            )
        )
        pending_review = await db.scalar(
            select(func.count(Application.id)).where(Application.status == "pending_review")
        )
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        applied_week = await db.scalar(
            select(func.count(Application.id)).where(
                Application.status.in_(["sent", "replied", "interview", "offer"]),
                Application.sent_at >= week_start,
            )
        )

        from backend.modules.notifier.telegram import notify_daily_digest
        await notify_daily_digest({
            "new_today": new_today or 0,
            "high_match": high_match or 0,
            "pending_review": pending_review or 0,
            "applied_week": applied_week or 0,
        })


# ─── Task: Follow-up Checker ──────────────────────────────────────────────────
async def check_follow_ups():
    """Alert about applications that have follow-ups due today."""
    async with AsyncSessionLocal() as db:
        today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

        result = await db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(
                Application.follow_up_due >= today_start,
                Application.follow_up_due <= today,
                Application.status.in_(["sent", "replied"]),
            )
        )
        follow_ups = [
            {"title": job.title, "company": job.company, "id": app.id}
            for app, job in result.fetchall()
        ]

        if follow_ups:
            from backend.modules.notifier.telegram import notify_follow_ups
            await notify_follow_ups(follow_ups)


# ─── Task: Weekly Cleanup ─────────────────────────────────────────────────────
async def autodelete_stale_jobs():
    """Daily purge of old jobs to keep DB lean."""
    async with AsyncSessionLocal() as db:
        # 1. Delete jobs older than 7 days that aren't in progress
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        res = await db.execute(
            select(Job).where(
                Job.found_at < seven_days_ago,
                Job.status.in_(["new", "reviewed", "shortlisted", "skipped"])
            )
        )
        stale_jobs = res.scalars().all()
        for job in stale_jobs:
            await db.delete(job)
        
        # 2. Daily cleanup of remnants
        await db.commit()
        if len(stale_jobs) > 0:
            logger.info(f"[Cleanup] Permanently deleted {len(stale_jobs)} stale jobs older than 7 days.")


# ─── Task: Gmail Reply Polling ────────────────────────────────────────────────
async def run_reply_polling():
    """Poll Gmail for recruiter replies."""
    from backend.modules.mailer.reply_detector import poll_for_replies
    async with AsyncSessionLocal() as db:
        await poll_for_replies(db)


# ─── Setup ────────────────────────────────────────────────────────────────────
def setup_scheduler():
    """Register all scheduled tasks."""
    # Scrape every 6 hours
    scheduler.add_job(
        run_job_scraper,
        trigger=CronTrigger(hour="0,6,12,18", minute=0),
        id="job_scraper",
        replace_existing=True,
    )

    # Processor worker every 5 minutes
    scheduler.add_job(
        run_processor_worker,
        trigger="interval",
        minutes=5,
        id="processor_worker",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # Daily digest at 9am UTC
    scheduler.add_job(
        send_daily_digest,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_digest",
        replace_existing=True,
    )

    # Follow-up check at 8am UTC
    scheduler.add_job(
        check_follow_ups,
        trigger=CronTrigger(hour=8, minute=0),
        id="follow_up_check",
        replace_existing=True,
    )

    # Daily cleanup at 2am UTC
    scheduler.add_job(
        autodelete_stale_jobs,
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_cleanup",
        replace_existing=True,
    )

    # Hourly Health Check
    scheduler.add_job(
        run_health_check,
        trigger=CronTrigger(minute=0), # every hour at :00
        id="health_check",
        replace_existing=True,
    )

    # Gmail Reply Polling every 2 hours
    scheduler.add_job(
        run_reply_polling,
        trigger="interval",
        hours=2,
        id="gmail_reply_polling",
        replace_existing=True,
    )

    logger.info("Scheduler configured with 4 tasks.")
    return scheduler
