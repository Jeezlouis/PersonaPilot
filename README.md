# 🎯 Job Automater (PersonaPilot)

**AI-powered job search & application assistant.** Finds, ranks, and drafts tailored applications using the right resume for every job.

---

## ✨ Features

-   **5+ scraper sources** — RemoteOK, Remotive, We Work Remotely, Indeed, and Hacker News.
-   **Multi-Layer Deduplication** — 3-layer filtering (Hash + URL + Semantic) to prevent duplicate applications across platforms.
-   **Weighted AI Scoring (0–100)** — Ranks jobs by skill match, role fit, recency, and historical **AI Memory** (lessons from past results).
-   **Persona-Aware Drafting** — Automatically chooses the right persona (Frontend, Backend, AI, etc.) and resume for every job.
-   **"No-Hallucination" AI Engine** — Gemini-powered cover letter and bullet point generator with strict factual enforcement.
-   **Telegram Workflow** — Unified bot for notifications, job screening, and status updates.
-   **Kanban Tracker** — Complete lifecycle management from Drafted &rarr; Interview &rarr; Offer/Rejected.
-   **Automated Scheduling** — Built-in Python scheduler + GitHub Actions for hands-free scraping every 6 hours.

---

## 📄 Documentation

For a deep technical dive into architectural patterns and AI instructions, see:
👉 **[PROJECT_GUIDE.md](./PROJECT_GUIDE.md)**

---

## 📁 Project Structure

```text
job_automater/
├── backend/
│   ├── api/                 # API Routes (Jobs, Resumes, Settings, etc.)
│   ├── modules/
│   │   ├── ai_engine/       # Gemini classifier, generator, and persona engine
│   │   ├── deduplicator/    # 3-layer semantic dedup logic
│   │   ├── scorer/          # Weighted ranking & AI memory signals
│   │   ├── scraper/         # Multi-source job intake & normalization
│   │   ├── resume_manager/  # Resume versioning & PDF processing
│   │   └── notifier/        # Telegram Bot integration
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # SQLAlchemy ORM (Jobs, Applications, Memory)
│   ├── database.py          # Database initialization & session management
│   ├── config.py            # Environment-driven settings
│   └── scheduler.py         # Periodic task orchestration
├── frontend/
│   ├── js/                  # SPA Logic (Dashboard, Kanban, Jobs, Notifications)
│   ├── css/                 # Modern design system (Vanilla CSS)
│   └── index.html           # Main Application Shell
├── data/
│   ├── resumes/             # User resume library (PDF/DOCX)
│   └── job_automater.db     # Local SQLite storage
├── .github/workflows/       # GitHub Actions (CI/CD + Periodic Scrapes)
├── scripts/                 # Utility scripts (check-limit, debug-gen, etc.)
├── PROJECT_GUIDE.md         # Technical architecture documentation
├── .env.example             # Clean environment template
└── requirements.txt         # Project dependencies
```

---

## 🧠 AI Decision Lifecycle

1.  **Ingest:** Scraper feeds new jobs into the system.
2.  **Filter:** Deduplicator runs checks to ensure uniqueness.
3.  **Classify:** Gemini categorizes the role into specific **Personas**.
4.  **Score:** Scorer ranks the job (0–100) based on persona-fit and skills.
5.  **Alert:** If Score > 80, the **Notifier** sends a Telegram message.
6.  **Draft:** Upon user click, the **AI Engine** generates a tailored application package.
7.  **Optimize:** AI Memory records results (interviews/rejections) to improve future scoring.

---

## 📊 Database (Core Tables)

| Table | High-Level Purpose |
| :--- | :--- |
| `jobs` | Master list of all scraped and processed job postings. |
| `applications` | Tracks job status, selected resumes, and drafted content. |
| `resumes` | Stores metadata and paths to tailored resume versions. |
| `ai_memory` | Long-term memory of past application outcomes for ranking. |
| `user_profiles` | Stores persona-based tone guidance and preferred keywords. |
| `platform_links` | Social profiles (GitHub, LinkedIn) to inject into drafts. |

---

## 🚀 API Quick Reference

Base URL: `http://localhost:8000/api`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/jobs` | List jobs with advanced filtering. |
| **POST** | `/jobs/:id/draft` | Generate AI-powered cover message/subject. |
| **PATCH** | `/jobs/:id/status` | Update job/application workflow status. |
| **GET** | `/applications/kanban` | Fetch jobs grouped by lifecycle stage. |
| **POST** | `/settings/scrape-now` | Manually trigger a scrape across all sources. |
| **GET** | `/health` | Check system and database health. |

---

## 🔐 Safety & Standards

-   **Manual Review Required:** Zero "auto-submission"—human approval is mandatory for every application.
-   **Privacy First:** All data stays local in your SQLite database.
-   **Persona Driven:** Your personality, tone, and links are fully customizable in Settings.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.11+**
- **[Google Gemini API Key](https://aistudio.google.com/)** (Free tier works perfectly)
- **[Telegram Bot](https://t.me/BotFather)** (Optional, for mobile alerts)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/job-automater.git
cd "Job automater"

# Setup virtual environment
python -m venv venv
venv\Scripts\activate # Windows
source venv/bin/activate # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Initialize environment
copy .env.example .env
```

### 3. Run
```bash
python -m backend.main
```
Visit: **http://localhost:8000**

---

## 📲 Telegram Integration

1.  Message **[@BotFather](https://t.me/BotFather)** &rarr; `/newbot`
2.  Copy your **API Token** and **Chat ID**.
3.  Add them to your `.env` file:
    ```env
    TELEGRAM_BOT_TOKEN=your_token
    TELEGRAM_CHAT_ID=your_id
    ```
4.  Run a test via the **Settings** page in the UI.

---

## ⚙️ GitHub Actions (Cron Scrape)

To enable automated scraping every 6 hours in the cloud:
1.  Go to your GitHub Repository **Settings** &rarr; **Secrets and variables** &rarr; **Actions**.
2.  Add the following **Secrets**:
    - `GEMINI_API_KEY`: Your Google AI key.
    - `TELEGRAM_BOT_TOKEN`: Your bot token.
    - `TELEGRAM_CHAT_ID`: Your chat ID.
3.  The workflow in `.github/workflows/scrape.yml` will now run automatically.
