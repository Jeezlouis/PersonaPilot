"""
config.py — Central settings loader using pydantic-settings.
All values read from .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os


class Settings(BaseSettings):
    # AI
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")

    # Telegram
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., env="TELEGRAM_CHAT_ID")

    # Scraper APIs
    adzuna_app_id: Optional[str] = Field(default=None, env="ADZUNA_APP_ID")
    adzuna_app_key: Optional[str] = Field(default=None, env="ADZUNA_APP_KEY")
    jooble_api_key: Optional[str] = Field(default=None, env="JOOBLE_API_KEY")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/job_automater.db",
        env="DATABASE_URL"
    )

    # App
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")
    debug: bool = Field(default=True, env="DEBUG")

    # Job preferences
    preferred_locations: str = Field(default="Remote,Worldwide", env="PREFERRED_LOCATIONS")
    min_match_score: int = Field(default=60, env="MIN_MATCH_SCORE")
    max_applications_per_day: int = Field(default=10, env="MAX_APPLICATIONS_PER_DAY")
    salary_min: int = Field(default=50000, env="SALARY_MIN")
    salary_max: int = Field(default=200000, env="SALARY_MAX")

    # Scraping
    search_keywords: str = Field(
        default="Software Engineer,Frontend Developer,Backend Developer,Full Stack Developer,AI Engineer",
        env="SEARCH_KEYWORDS"
    )
    scrape_mode: str = Field(default="local", env="SCRAPE_MODE") # local | cloud
    salary_minimum: int = Field(default=60000, env="SALARY_MINIMUM")
    target_seniority: str = Field(default="junior,mid,senior", env="TARGET_SENIORITY")
    
    scrape_delay: float = Field(default=2.0, env="SCRAPE_DELAY")
    user_agent: str = Field(
        default="JobAutomater/1.0 (Personal job search tool)",
        env="USER_AGENT"
    )

    # Candidate profile (for form filling)
    candidate_first_name: str = Field(default="", env="CANDIDATE_FIRST_NAME")
    candidate_last_name: str = Field(default="", env="CANDIDATE_LAST_NAME")
    candidate_email: str = Field(default="", env="CANDIDATE_EMAIL")
    candidate_phone: str = Field(default="", env="CANDIDATE_PHONE")
    candidate_linkedin: str = Field(default="", env="CANDIDATE_LINKEDIN")
    candidate_github: str = Field(default="", env="CANDIDATE_GITHUB")

    # Feature flags
    enable_enrichment: bool = Field(default=True, env="ENABLE_ENRICHMENT")
    enable_autofill: bool = Field(default=True, env="ENABLE_AUTOFILL")
    enable_embeddings: bool = Field(default=True, env="ENABLE_EMBEDDINGS")

    # Resumes
    resume_dir: str = Field(default="./data/resumes", env="RESUME_DIR")

    # Application mode
    application_mode: str = Field(default="draft", env="APPLICATION_MODE")
    email_outreach_interval_days: int = Field(default=60, env="EMAIL_OUTREACH_INTERVAL_DAYS")

    # Email (optional)
    email_host: Optional[str] = Field(default=None, env="EMAIL_HOST")
    email_port: int = Field(default=587, env="EMAIL_PORT")
    email_user: Optional[str] = Field(default=None, env="EMAIL_USER")
    email_password: Optional[str] = Field(default=None, env="EMAIL_PASSWORD")

    # Platform links (defaults, updated via DB/UI)
    github_url: str = Field(default="", env="GITHUB_URL")
    portfolio_url: str = Field(default="", env="PORTFOLIO_URL")
    linkedin_url: str = Field(default="", env="LINKEDIN_URL")

    @property
    def preferred_locations_list(self) -> List[str]:
        return [loc.strip() for loc in self.preferred_locations.split(",") if loc.strip()]

    @property
    def search_keywords_list(self) -> List[str]:
        return [kw.strip() for kw in self.search_keywords.split(",") if kw.strip()]

    @property
    def target_seniority_list(self) -> List[str]:
        return [s.strip().lower() for s in self.target_seniority.split(",") if s.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Ensure required directories exist
os.makedirs(settings.resume_dir, exist_ok=True)
os.makedirs("./data", exist_ok=True)
os.makedirs("./logs", exist_ok=True)
