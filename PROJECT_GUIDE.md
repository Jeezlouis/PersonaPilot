# 📄 Project Documentation: Job Automater (PersonaPilot)

This document provides a technical overview of the **Job Automater** project (internally named PersonaPilot). It is designed to give an AI assistant full context for providing architectural, feature, or code-level advice.

---

## 1. 🎯 Project Overview
**Job Automater** is an AI-powered job search and application assistant. It automates the "tedious" parts of job hunting—finding, filtering, ranking, and drafting tailored applications—while keeping the user "in the loop" for the final decision.

**Key Objective:** High-quality, tailored volume. Applying to more jobs with higher precision by using specific personas and multiple resume versions.

---

## 2. 🛠 Tech Stack
- **Backend:** Python 3.11+ using **FastAPI**.
- **Database:** **SQLite** with **SQLAlchemy 2.0** (Asyncio).
- **AI Engine:** **Google Gemini (flash-latest)** for classification and content generation.
- **Frontend:** Vanilla HTML5, CSS3, and JavaScript (SPA architecture).
- **Automation:** **APScheduler** for local periodic tasks; **GitHub Actions** for cloud-based scraping.
- **Notifications:** **Telegram Bot API**.

---

## 3. 📂 System Architecture & Modules

### A. Scraper Module (`backend/modules/scraper/`)
- Integrates with 5+ sources: RemoteOK, Remotive, We Work Remotely, Indeed, and Hacker News.
- Standardizes diverse job payloads into a unified `Job` schema.
- Handles rate limiting and source-specific parsing logic.

### B. Deduplicator Module (`backend/modules/deduplicator/`)
Prevents redundant applications using 3 layers:
1. **Hash Check:** Exact content matching.
2. **URL Check:** Duplicate source links.
3. **Semantic Check:** Detects the same job posted across different platforms/URLs.

### C. Scorer Module (`backend/modules/scorer/`)
Ranks jobs on a 0–100 scale using weighted signals:
- **Skill Match:** Overlap between job requirements and resume skills.
- **Role Fit:** Alignment with preferred personas (Frontend, Backend, etc.).
- **Recency:** Bonus for newer postings.
- **Memory Signals:** Adjusts scores based on historical success/rejections from similar companies/roles.

### D. AI Engine (`backend/modules/ai_engine/`)
The "brain" of the system using Gemini:
- **Classifier:** Categorizes jobs into roles (AI, DevOps, Fullstack, etc.).
- **Selector:** Picks the optimal resume from the user's library (`data/resumes/`).
- **Generator:** Produces tailored cover messages, email subjects, and resume bullets using a "No-Hallucination" prompt policy.

### E. Notifier Module (`backend/modules/notifier/`)
- Structured Telegram alerts for high-score matches (Score > 80).
- Allows for quick "Skip" or "Review" actions via the bot.

---

## 4. 🧠 Core AI Logic (Gemini Prompts)

### No-Hallucination Policy
The `content_gen.py` module enforces strict rules to prevent the AI from fabricating skills:
- *Rule:* "NEVER fabricate experience, skills, or achievements not in the resume."
- *Rule:* "Do not start with 'I am writing to...'" (Prevents generic AI patterns).

### Persona-Aware Tones
Applications are tuned based on the role:
- **Frontend:** Highlights UI craftsmanship and visual excellence.
- **Backend:** Focuses on API design, scalability, and reliability.
- **AI:** Focuses on automation and LLM efficiency.

---

## 5. 🔄 Data Flow (Lifecycle)
1. **Scrape:** Scheduler triggers scrapers every 6 hours.
2. **Ingest & Clean:** Jobs are normalized and deduplicated.
3. **Classify:** AI categorizes the role; Scorer assigns a priority.
4. **Notify:** High-priority matches are sent to Telegram.
5. **Draft:** Upon user request (via UI), the AI drafts a tailored application package.
6. **Track:** User moves the job through the Kanban board (Drafted → Applied → Interview → Offer/Rejected).

---

## 6. 📊 Database Schema (Highlights)
- `jobs`: Stores all metadata including `score`, `role_category`, and `raw_description`.
- `applications`: Links a job to a specific `resume` and tracks `status`.
- `resumes`: Metadata and paths to PDF/DOCX versions.
- `ai_memory`: Stores feedback loops to improve future scoring.

---

## 7. 🚀 Future Roadmap / Advice Areas
- **Direct Mail Integration:** Automating the sending phase (Gmail/Outlook API).
- **Browser Automation:** Using Playwright for auto-filling application forms.
- **Deeper Skill Extraction:** Moving from keyword matching to vector-based semantic overlap for scoring.
- **Multi-Persona Profiles:** Handling users with completely different career tracks.
