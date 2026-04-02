# 🎯 Job Automater

**AI-powered job search & application assistant.** Finds, ranks, and drafts tailored applications using the right resume for every job.

---

## ✨ Features

- **5 scraper sources** — RemoteOK, Remotive, We Work Remotely, Indeed, Hacker News
- **AI classification** — Gemini classifies each job: frontend, backend, fullstack, AI, devops
- **Smart resume selection** — Matches your best resume to each job automatically
- **Persona-aware drafts** — Cover messages adapt tone per role type (UI focus, API focus, etc.)
- **3-layer deduplication** — Hash + URL + semantic checks prevent duplicates
- **Weighted scoring** — Ranks jobs by skill match, role fit, recency, salary, and memory signals
- **AI memory** — Learns from past outcomes (replies, interviews, rejections)
- **Telegram notifications** — Structured alerts for new matches, drafts, follow-ups
- **Kanban tracker** — Full lifecycle from drafted → offer/rejected
- **GitHub Actions** — Automated scraping every 6 hours

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- [Google Gemini API Key](https://aistudio.google.com/) (free)
- [Telegram Bot Token](https://t.me/BotFather) + your Chat ID

### 2. Setup

```bash
# Clone / open the project
cd "Job automater"

# Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# or: source venv/bin/activate (Linux/Mac)

# Install dependencies
pip install -r requirements.txt

# Copy and fill in your .env
copy .env.example .env
```

### 3. Configure `.env`

Open `.env` and set at minimum:

```
GEMINI_API_KEY=your_gemini_api_key_here
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. Run

```bash
python -m backend.main
```

Visit: **http://localhost:8000**

---

## 📁 Project Structure

```
job_automater/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings from .env
│   ├── database.py          # SQLite async engine
│   ├── models.py            # 8 ORM tables
│   ├── scheduler.py         # APScheduler tasks
│   └── modules/
│       ├── scraper/         # 5 job scrapers + normalizer
│       ├── deduplicator/    # 3-layer dedup
│       ├── scorer/          # Weighted 0-100 scorer
│       ├── ai_engine/       # Gemini classifier, selector, generator, memory
│       ├── resume_manager/  # PDF/DOCX extraction + CRUD
│       └── notifier/        # Telegram bot
├── frontend/
│   ├── index.html           # SPA shell
│   ├── css/style.css        # Full design system
│   └── js/                  # Page modules
├── data/
│   ├── resumes/             # Uploaded resume files
│   └── job_automater.db     # SQLite database
└── .github/workflows/       # GitHub Actions cron
```

---

## 🖥 UI Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Stats, category breakdown, top-match jobs |
| **Jobs** | Filterable list with score rings and AI draft button |
| **Tracker** | 8-column Kanban from drafted → offer/rejected |
| **Notifications** | Telegram message log with mark-read |
| **Settings** | Resume upload, platform links, personas, system controls |

---

## 🧠 AI Decision Flow

```
Job Found
    │
    ▼
Classify role (Gemini)
    │
    ▼
Score job (0–100)
    │
    ├─ < 60 → Auto-skip
    │
    ├─ 60-79 → Surface in UI (manual review)
    │
    └─ 80+ → Telegram notification + surface in UI
                │
                ▼
        Select best resume (AI + skill overlap)
                │
                ▼
        Generate draft (cover + bullets + subject)
                │
                ▼
        YOU REVIEW → YOU DECIDE TO SEND
```

---

## 📲 Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Copy the token → set `TELEGRAM_BOT_TOKEN` in `.env`
3. Start your bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Copy the `chat.id` → set `TELEGRAM_CHAT_ID` in `.env`
5. Test via Settings page → **Test Telegram**

---

## 🔐 Safety Rules

- ❌ **No auto-submit** — every application requires your manual approval
- ❌ **No double-applying** — enforced by hash + URL dedup at every level
- ❌ **Max 10 applications/day** (configurable in `.env`)
- ✅ **Draft-first mode** — AI only drafts, you copy-paste and send
- ✅ **Risky actions require confirmation** (deletes, skips)

---

## ⚙️ GitHub Actions Secrets

Add these in your GitHub repo → Settings → Secrets → Actions:

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Google AI Studio key |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

---

## 📊 Database Tables

| Table | Purpose |
|-------|---------|
| `jobs` | All discovered jobs |
| `applications` | Application lifecycle |
| `resumes` | Your resume files + metadata |
| `ai_memory` | Past outcomes for scoring |
| `user_profiles` | Your personas/roles |
| `platform_links` | GitHub, portfolio, etc. |
| `notifications` | Telegram message log |
| `scheduler_runs` | Cron run history |

---

## 🛠 API Reference

Base URL: `http://localhost:8000/api`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List jobs with filters |
| GET | `/jobs/stats` | Dashboard stats |
| GET | `/jobs/:id` | Job detail + application |
| POST | `/jobs/:id/draft` | Generate AI application |
| PATCH | `/jobs/:id/status` | Update job status |
| GET | `/applications/kanban` | Kanban grouped view |
| PATCH | `/applications/:id` | Update application status |
| GET | `/resumes` | List resumes |
| POST | `/resumes/upload` | Upload resume file |
| GET | `/settings/links` | Platform links |
| POST | `/settings/scrape-now` | Manual scrape trigger |
| POST | `/settings/test-telegram` | Test Telegram |

Interactive docs: **http://localhost:8000/docs**
