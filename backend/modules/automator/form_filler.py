"""
form_filler.py — Automation engine using Playwright.
Supports Greenhouse, Lever, and Ashby form pre-filling.
Strictly follows the "NO AUTO-SUBMIT" policy.
"""
import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from playwright.async_api import async_playwright
from backend.config import settings

logger = logging.getLogger(__name__)

# Ensure screenshot directory exists
SCREENSHOT_DIR = Path("./data/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

async def prefill_form(job_url: str, resume_path: str, cover_letter: str) -> Dict[str, Any]:
    """
    Open the job URL, detect the ATS, and pre-fill the application form.
    Returns: {screenshot_path, status, error}
    """
    async with async_playwright() as p:
        # Launch browser (headless=True for production, False for debugging)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        try:
            logger.info(f"[Autofill] Navigating to {job_url}...")
            await page.goto(job_url, wait_until="networkidle", timeout=45000)

            # 1. Detect ATS
            ats_type = _detect_ats(page.url, await page.content())
            logger.info(f"[Autofill] Detected ATS: {ats_type}")

            if ats_type == "unknown":
                return {"status": "error", "error": "Unsupported ATS or no form found."}

            # 2. Fill the form
            if ats_type == "greenhouse":
                await _fill_greenhouse(page, resume_path, cover_letter)
            elif ats_type == "lever":
                await _fill_lever(page, resume_path, cover_letter)
            elif ats_type == "ashby":
                await _fill_ashby(page, resume_path, cover_letter)

            # 3. Take screenshot for human review
            screenshot_name = f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot_path = SCREENSHOT_DIR / screenshot_name
            await page.screenshot(path=str(screenshot_path), full_page=True)

            return {
                "status": "success",
                "ats": ats_type,
                "screenshot_path": str(screenshot_path),
                "page_url": page.url
            }

        except Exception as e:
            logger.error(f"[Autofill] Failed: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            await browser.close()

def _detect_ats(url: str, html: str) -> str:
    """Detect which application tracking system is being used."""
    url_lower = url.lower()
    html_lower = html.lower()

    if "greenhouse.io" in url_lower or "boards.greenhouse.io" in url_lower or 'id="grnhse_app"' in html_lower:
        return "greenhouse"
    if "lever.co" in url_lower or 'class="lever-job"' in html_lower:
        return "lever"
    if "ashbyhq.com" in url_lower or 'id="ashby-job-board"' in html_lower:
        return "ashby"
    
    return "unknown"

async def _fill_greenhouse(page, resume_path: str, cover_letter: str):
    """Fill specialized Greenhouse fields."""
    # Common selectors
    await page.fill('input[id="first_name"]', settings.candidate_first_name)
    await page.fill('input[id="last_name"]', settings.candidate_last_name)
    await page.fill('input[id="email"]', settings.candidate_email)
    await page.fill('input[id="phone"]', settings.candidate_phone)
    
    # Custom fields (LinkedIn, Portfolio)
    await page.fill('input[name*="job_application[answers_attributes]"][name*="[text_value]"]', settings.candidate_linkedin)
    
    # Resume Upload
    async with page.expect_file_chooser() as fc_info:
        await page.click('button[data-source="attach"]')
    file_chooser = await fc_info.value
    await file_chooser.set_files(resume_path)

    # Cover Letter (if text area exists)
    if await page.query_selector('textarea[id="cover_letter_text"]'):
        await page.fill('textarea[id="cover_letter_text"]', cover_letter)

async def _fill_lever(page, resume_path: str, cover_letter: str):
    """Fill specialized Lever fields."""
    # Lever usually has a two-step flow or a long page
    await page.fill('input[name="name"]', f"{settings.candidate_first_name} {settings.candidate_last_name}")
    await page.fill('input[name="email"]', settings.candidate_email)
    await page.fill('input[name="phone"]', settings.candidate_phone)
    await page.fill('input[name="org"]', "Independent")

    # Resume
    async with page.expect_file_chooser() as fc_info:
        await page.click('input[type="file"]')
    file_chooser = await fc_info.value
    await file_chooser.set_files(resume_path)

    # Links
    await page.fill('input[name="urls[LinkedIn]"]', settings.candidate_linkedin)
    await page.fill('input[name="urls[GitHub]"]', settings.candidate_github)

async def _fill_ashby(page, resume_path: str, cover_letter: str):
    """Fill specialized Ashby fields."""
    # Ashby uses complex React forms; selectors target common ARIA labels or IDs
    await page.fill('input[name="first_name"]', settings.candidate_first_name)
    await page.fill('input[name="last_name"]', settings.candidate_last_name)
    await page.fill('input[name="email"]', settings.candidate_email)
    
    # Resume
    async with page.expect_file_chooser() as fc_info:
        await page.click('button:has-text("Upload Resume")')
    file_chooser = await fc_info.value
    await file_chooser.set_files(resume_path)
