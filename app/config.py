import os
from typing import List


class Settings:
    """Application configuration settings."""

    APP_NAME: str = "Website Analyzer API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "AI-powered website analyzer that compares websites and identifies "
        "customer journey flaws"
    )

    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Analysis settings
    BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "30000"))  # ms
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    SCREENSHOT_ENABLED: bool = os.getenv("SCREENSHOT_ENABLED", "true").lower() == "true"

    # Storage settings
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")
    MAX_HISTORY_ITEMS: int = int(os.getenv("MAX_HISTORY_ITEMS", "100"))

    # CORS settings
    ALLOWED_ORIGINS: List[str] = os.getenv(
        "ALLOWED_ORIGINS", "*"
    ).split(",")

    # Performance thresholds
    GOOD_LOAD_TIME_MS: int = 2000
    ACCEPTABLE_LOAD_TIME_MS: int = 4000

    # Scoring weights
    SCORE_WEIGHTS = {
        "navigation": 0.15,
        "forms": 0.15,
        "performance": 0.20,
        "accessibility": 0.20,
        "mobile_ux": 0.15,
        "content": 0.10,
        "cta": 0.05,
    }


settings = Settings()
