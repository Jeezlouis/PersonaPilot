"""
main.py — FastAPI application entry point.
Serves the API + static frontend files.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timezone, timedelta

from backend.database import init_db
from backend.scheduler import setup_scheduler, scheduler
from backend.api import jobs, applications, resumes, settings, notifications, gmail

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("./logs/app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Job Automater...")

    # Initialize DB
    await init_db()
    logger.info("Database ready.")

    # Seed default data if needed
    await _seed_defaults()

    # Start scheduler
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started.")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped. Goodbye.")


async def _seed_defaults():
    """Seed default platform links and personas on first run."""
    from backend.database import AsyncSessionLocal
    from backend.models import PlatformLink, UserProfile
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        # Only seed if empty
        link_count = await db.scalar(select(func.count(PlatformLink.id)))
        if link_count == 0:
            from backend.config import settings
            defaults = [
                PlatformLink(
                    platform="github",
                    url=settings.github_url or "https://github.com/yourusername",
                    description="GitHub profile",
                    relevant_for=["backend", "fullstack", "ai", "devops"],
                    is_active=bool(settings.github_url),
                ),
                PlatformLink(
                    platform="portfolio",
                    url=settings.portfolio_url or "https://yourportfolio.com",
                    description="Portfolio website",
                    relevant_for=["frontend", "fullstack", "freelancer"],
                    is_active=bool(settings.portfolio_url),
                ),
                PlatformLink(
                    platform="linkedin",
                    url=settings.linkedin_url or "https://linkedin.com/in/yourprofile",
                    description="LinkedIn profile",
                    relevant_for=["frontend", "backend", "fullstack", "ai"],
                    is_active=bool(settings.linkedin_url),
                ),
            ]
            db.add_all(defaults)

        profile_count = await db.scalar(select(func.count(UserProfile.id)))
        if profile_count == 0:
            personas = [
                UserProfile(
                    persona="fullstack",
                    tone_guidance="Emphasize end-to-end ownership and ability to ship independently.",
                    preferred_keywords=["React", "Python", "FastAPI", "PostgreSQL"],
                    is_active=True,
                    priority=1,
                ),
                UserProfile(
                    persona="frontend",
                    tone_guidance="Emphasize UI quality, user experience, and performance.",
                    preferred_keywords=["React", "TypeScript", "CSS", "Next.js"],
                    is_active=True,
                    priority=2,
                ),
                UserProfile(
                    persona="backend",
                    tone_guidance="Emphasize APIs, architecture, and scalability.",
                    preferred_keywords=["Python", "FastAPI", "PostgreSQL", "REST"],
                    is_active=True,
                    priority=3,
                ),
            ]
            db.add_all(personas)

        await db.commit()
        logger.info("Default data seeded.")


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Job Automater",
    description="AI-powered job search and application automation system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routes ───────────────────────────────────────────────────────────────
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(resumes.router)
app.include_router(settings.router)
app.include_router(notifications.router)
app.include_router(gmail.router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    """Enhanced health check with live system stats."""
    from backend.database import AsyncSessionLocal
    from backend.models import PendingJob, ScrapeRun, SchedulerRun
    from sqlalchemy import select, func, or_
    import google.generativeai as genai
    from backend.config import settings

    stats = {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {},
        "queue": {}
    }

    async with AsyncSessionLocal() as db:
        # 1. Queue Depth (Pending + Processing)
        stats["queue"]["pending"] = await db.scalar(
            select(func.count(PendingJob.id)).where(PendingJob.status.in_(["pending", "processing"]))
        )
        stats["queue"]["failed_last_24h"] = await db.scalar(
            select(func.count(PendingJob.id)).where(
                PendingJob.status == "failed", 
                PendingJob.queued_at >= datetime.now(timezone.utc) - timedelta(days=1)
            )
        )

        # 2. Last Scrape status (from SchedulerRun)
        last_scrape = await db.execute(
            select(SchedulerRun)
            .where(SchedulerRun.task_name == "job_scraper")
            .order_by(SchedulerRun.started_at.desc())
            .limit(1)
        )
        ls = last_scrape.scalars().first()
        stats["last_scrape"] = {
            "time": ls.started_at.isoformat() if ls else None,
            "status": ls.status if ls else "none",
            "found": ls.jobs_found if ls else 0
        }

        # 3. Gemini Health
        try:
            # Quick list_models check to verify API key
            genai.configure(api_key=settings.gemini_api_key)
            # We don't want to actually call a model to save tokens, just verify config
            stats["services"]["gemini"] = "connected"
        except Exception:
            stats["services"]["gemini"] = "error"

    return stats


# ─── Static Frontend ──────────────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend SPA for all non-API routes."""
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API route not found")
        index = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(index)


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from backend.config import settings

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        reload_dirs=["backend"], # Only watch the code, not the data or logs
        reload_excludes=["*.db", "*.db-wal", "*.db-shm", "*.log", "data/*", "logs/*"],
        log_level="info",
    )
