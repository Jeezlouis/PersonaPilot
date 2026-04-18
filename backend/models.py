"""
models.py — All 8 SQLAlchemy ORM models (SQLite).
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Text, JSON, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# 1. Jobs
# ─────────────────────────────────────────────
class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False)           # remoteok, indeed, etc.
    source_id = Column(String(256), nullable=True)        # source's own ID
    url = Column(String(1024), nullable=False)
    title = Column(String(256), nullable=False)
    company = Column(String(256), nullable=True)
    location = Column(String(256), nullable=True)
    job_type = Column(String(32), nullable=True)          # remote, hybrid, onsite
    employment_type = Column(String(32), nullable=True)   # full-time, part-time, freelance, contract
    role_category = Column(String(64), nullable=True)     # frontend, backend, fullstack, ai, other
    description = Column(Text, nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    found_at = Column(DateTime(timezone=True), default=utcnow)
    status = Column(String(32), default="new")            # new, reviewed, shortlisted, skipped, applied
    match_score = Column(Float, default=0.0)
    hash_id = Column(String(64), unique=True, index=True) # dedup hash
    tags = Column(JSON, default=list)
    raw_data = Column(JSON, nullable=True)
    contact_email = Column(String(256), nullable=True)
    contact_confidence = Column(String(32), default="none")  # "direct", "inferred", "none"

    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="job", cascade="all, delete-orphan")
    outreach = relationship("EmailOutreach", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_status_score", "status", "match_score"),
        Index("ix_jobs_found_at", "found_at"),
    )


# ─────────────────────────────────────────────
# 2. Applications
# ─────────────────────────────────────────────
class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)

    # Status pipeline
    status = Column(String(32), default="drafted")
    # drafted → pending_review → approved → sent → replied → interview → offer → rejected

    cover_message = Column(Text, nullable=True)
    email_subject = Column(String(256), nullable=True)
    tailored_bullets = Column(JSON, nullable=True)         # list of tweaked resume bullets
    tailored_resume_path = Column(String(512), nullable=True)

    # Timestamps
    sent_at = Column(DateTime(timezone=True), nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    interview_at = Column(DateTime(timezone=True), nullable=True)
    follow_up_due = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    notes = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)       # AI confidence in resume match

    job = relationship("Job", back_populates="applications")
    resume = relationship("Resume", back_populates="applications")


# ─────────────────────────────────────────────
# 3. Resumes
# ─────────────────────────────────────────────
class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    role_type = Column(String(64), nullable=False)        # frontend, backend, fullstack, ai, freelancer
    skills = Column(JSON, default=list)                   # ["React", "TypeScript", ...]
    experience_summary = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=True)
    content_text = Column(Text, nullable=True)            # extracted plain text
    tags = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    applications = relationship("Application", back_populates="resume")


# ─────────────────────────────────────────────
# 4. AI Memory
# ─────────────────────────────────────────────
class AIMemory(Base):
    __tablename__ = "ai_memory"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(32), nullable=False)       # applied, skipped, replied, interviewed, rejected
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)
    outcome = Column(String(32), nullable=True)           # positive, negative, neutral
    keywords = Column(JSON, default=list)                 # keywords that contributed
    role_category = Column(String(64), nullable=True)
    company = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    notes = Column(Text, nullable=True)


# ─────────────────────────────────────────────
# 5. User Profiles / Personas
# ─────────────────────────────────────────────
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    persona = Column(String(64), nullable=False)          # frontend, backend, fullstack, ai, freelancer
    tone_guidance = Column(Text, nullable=True)           # how to position this persona
    preferred_keywords = Column(JSON, default=list)
    avoided_keywords = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=5)                 # 1 = highest, 10 = lowest
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ─────────────────────────────────────────────
# 6. Platform Links
# ─────────────────────────────────────────────
class PlatformLink(Base):
    __tablename__ = "platform_links"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(64), nullable=False)         # github, portfolio, linkedin, upwork, fiverr
    url = Column(String(1024), nullable=False)
    description = Column(String(256), nullable=True)
    relevant_for = Column(JSON, default=list)             # ["frontend", "backend"] etc.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ─────────────────────────────────────────────
# 7. Notifications
# ─────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(64), nullable=False)             # new_jobs, application_drafted, follow_up, error
    title = Column(String(256), nullable=False)
    message = Column(Text, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    telegram_message_id = Column(String(64), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    job = relationship("Job", back_populates="notifications")


# ─────────────────────────────────────────────
# 8. Scheduler Runs
# ─────────────────────────────────────────────
class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(128), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="running")        # running, success, failed
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


# ─────────────────────────────────────────────
# 9. Pending Jobs (Queue)
# ─────────────────────────────────────────────
class PendingJob(Base):
    __tablename__ = "pending_jobs"

    id = Column(Integer, primary_key=True, index=True)
    raw_data = Column(JSON, nullable=False)           # JSON blob from scraper
    source = Column(String(64), nullable=False)
    queued_at = Column(DateTime(timezone=True), default=utcnow)
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    status = Column(String(32), default="pending")    # pending | processing | done | failed


# ─────────────────────────────────────────────
# 10. Embedding Cache
# ─────────────────────────────────────────────
class EmbeddingCache(Base):
    __tablename__ = "embeddings_cache"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(256), nullable=False)   # job_id or resume_id
    source_type = Column(String(32), nullable=False)  # job | resume
    vector = Column(JSON, nullable=False)             # vector as list
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ─────────────────────────────────────────────
# 11. Scrape Runs
# ─────────────────────────────────────────────
class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    jobs_deduplicated = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    status = Column(String(32), default="running")    # running | success | failed

# ─────────────────────────────────────────────
# 12. Email Outreach
# ─────────────────────────────────────────────
class EmailOutreach(Base):
    __tablename__ = "email_outreach"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    recipient_email = Column(String(256), nullable=False)
    subject = Column(String(256), nullable=False)
    body = Column(Text, nullable=True)
    body_preview = Column(String(100), nullable=True)
    resume_used = Column(String(512), nullable=True)
    sent_at = Column(DateTime(timezone=True), default=utcnow)
    status = Column(String(32), default="drafted") # drafted|sent|bounced|replied
    gmail_message_id = Column(String(128), nullable=True)
    reply_received_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="outreach")

# ─────────────────────────────────────────────
# 13. AI Process Cache
# ─────────────────────────────────────────────
class AIProcessCache(Base):
    __tablename__ = "ai_process_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(256), unique=True, index=True) # e.g. "classify:{job_hash}"
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
