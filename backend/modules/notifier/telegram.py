"""
telegram.py — Telegram bot notification system.
Sends structured notifications for job events.
"""
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx
import os
import json

from backend.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def _send_message(text: str, parse_mode: str = "HTML") -> Optional[Dict]:
    """Send a message to the configured Telegram chat."""
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_telegram_bot_token_here":
        logger.warning("Telegram not configured. Skipping notification.")
        return None

    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return None


def _score_bar(score: float) -> str:
    """Visual score bar: ████░░░ 74%"""
    filled = int(score / 10)
    empty = 10 - filled
    return f"{'█' * filled}{'░' * empty} {score:.0f}%"


async def notify_new_jobs(jobs: List[Dict[str, Any]]) -> None:
    """Send notification for newly found high-match jobs."""
    if not jobs:
        return

    count = len(jobs)
    header = f"🆕 <b>{count} new {'job' if count == 1 else 'jobs'} found</b>\n{'━' * 24}\n"

    lines = []
    for i, job in enumerate(jobs[:5], 1):  # Max 5 per notification
        score = job.get("match_score", 0)
        job_type = job.get("job_type", "").capitalize()
        salary = ""
        if job.get("salary_min") and job.get("salary_max"):
            salary = f" | ${int(job['salary_min']//1000)}k-${int(job['salary_max']//1000)}k"

        lines.append(
            f"{i}. <b>{job.get('title', 'Unknown')}</b> @ {job.get('company', 'N/A')}\n"
            f"   {_score_bar(score)} | {job_type}{salary}\n"
            f"   🔗 <a href='{job.get('url', '#')}'>View Job</a>"
        )

    message = header + "\n\n".join(lines)
    await _send_message(message)
    logger.info(f"Telegram: notified {min(count, 5)} new jobs")


async def notify_application_drafted(job_title: str, company: str, resume_name: str) -> None:
    """Notify that an application draft is ready for review."""
    message = (
        f"✅ <b>Application Draft Ready</b>\n"
        f"{'━' * 24}\n"
        f"📋 <b>{job_title}</b> @ {company}\n"
        f"📄 Resume: {resume_name}\n\n"
        f"Review it in the app before approving."
    )
    await _send_message(message)


async def notify_follow_ups(follow_ups: List[Dict[str, Any]]) -> None:
    """Send daily follow-up reminder."""
    if not follow_ups:
        return
    lines = [f"• {f['title']} @ {f['company']}" for f in follow_ups[:5]]
    message = (
        f"📬 <b>{len(follow_ups)} follow-up{'s' if len(follow_ups) > 1 else ''} due today</b>\n"
        f"{'━' * 24}\n"
        + "\n".join(lines)
        + "\n\nCheck the tracker in your app."
    )
    await _send_message(message)


async def notify_error(task_name: str, error: str) -> None:
    """Notify about system errors."""
    message = (
        f"🚨 <b>System Error</b>\n"
        f"{'━' * 24}\n"
        f"Task: <code>{task_name}</code>\n"
        f"Error: <code>{error[:200]}</code>\n\n"
        f"Check logs for details."
    )
    await _send_message(message)


async def notify_daily_digest(stats: Dict[str, Any]) -> None:
    """Send morning digest with today's stats."""
    message = (
        f"☀️ <b>Daily Digest — {datetime.now().strftime('%b %d, %Y')}</b>\n"
        f"{'━' * 24}\n"
        f"📊 New jobs today: <b>{stats.get('new_today', 0)}</b>\n"
        f"⭐ High matches (80+): <b>{stats.get('high_match', 0)}</b>\n"
        f"📝 Drafts pending review: <b>{stats.get('pending_review', 0)}</b>\n"
        f"📤 Applied this week: <b>{stats.get('applied_week', 0)}</b>\n\n"
        f"Open the dashboard to review."
    )
    await _send_message(message)


async def notify_review_form(
    job_id: int, 
    title: str, 
    company: str, 
    screenshot_path: str,
    form_url: str
) -> bool:
    """
    Send a screenshot of the pre-filled form to Telegram for manual approval.
    Includes inline buttons for Apply/Edit/Reject.
    """
    if not settings.telegram_bot_token or not os.path.exists(screenshot_path):
        return False

    url = f"{TELEGRAM_API}/sendPhoto"
    
    # Text Caption
    caption = (
        f"📝 <b>Review Application Form</b>\n"
        f"{'━' * 24}\n"
        f"🎯 <b>{title}</b> @ {company}\n"
        f"🔗 <a href='{form_url}'>Open Form Link</a>\n\n"
        f"The form has been pre-filled. Review the screenshot below and approve the submission."
    )

    # Inline Keyboard
    # Since we don't have a webhook, these could be deep links to the local UI.
    # For now, we'll provide the link to the dashboard.
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "url": f"{settings.app_host}:{settings.app_port}/jobs/{job_id}?action=approve"},
            {"text": "📋 Edit", "url": f"{settings.app_host}:{settings.app_port}/jobs/{job_id}"},
            {"text": "❌ Skip", "callback_data": f"skip_{job_id}"}
        ]]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(screenshot_path, "rb") as photo:
                files = {"photo": photo}
                data = {
                    "chat_id": settings.telegram_chat_id,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps(reply_markup)
                }
                resp = await client.post(url, data=data, files=files)
                resp.raise_for_status()
                return True
    except Exception as e:
        logger.error(f"Telegram photo send failed: {e}")
        return False


async def notify_email_approval(job_id: int, title: str, company: str, to: str, subject: str, body_preview: str, resume_name: str) -> bool:
    """Send an email draft to Telegram for manual approval."""
    if not settings.telegram_bot_token:
        return False
        
    caption = (
        f"📧 <b>Cold Email Draft Ready</b>\n"
        f"{'━' * 24}\n"
        f"🎯 <b>{title}</b> @ {company}\n"
        f"To: {to}\n"
        f"Subject: <code>{subject}</code>\n"
        f"Resume: {resume_name}\n\n"
        f"<b>Preview:</b>\n<i>{body_preview}</i>"
    )
    
    reply_markup = {
        "inline_keyboard": [[
            {"text": "📨 Send Now", "url": f"http://localhost:{settings.app_port}/api/jobs/{job_id}/email/send"},
            {"text": "❌ Skip", "url": f"http://localhost:{settings.app_port}/api/jobs/{job_id}/email/skip"}
        ]]
    }
    
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": caption,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(reply_markup),
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Telegram email approval send failed: {e}")
        return False


async def test_connection() -> bool:
    """Test if the Telegram bot is configured and working."""
    result = await _send_message("🤖 Job Automater is connected and running!")
    return result is not None
