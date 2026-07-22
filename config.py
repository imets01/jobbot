"""
config.py
---------
Central configuration and shared constants for the job-scanning bot.

Loads environment variables via python-dotenv so that secrets (like the
Anthropic API key) are never hard-coded and never committed to Git.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local `.env` file (git-ignored) into the environment.
load_dotenv()

# --- Paths -----------------------------------------------------------------

# Project root (directory containing this file).
BASE_DIR = Path(__file__).resolve().parent

# Directory where raw scraped job JSON files are stored. Git-ignored.
DATA_DIR = BASE_DIR / "data"

# Uploaded CVs are private local artifacts stored below the ignored data folder.
CV_DIR = DATA_DIR / "cv"
MAX_CV_SIZE_BYTES = 10 * 1024 * 1024

# Local-first SQLite database used by the web application.
DATABASE_PATH = Path(os.getenv("JOBBOT_DATABASE_PATH", BASE_DIR / "jobbot.db"))
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# --- Secrets ---------------------------------------------------------------

# Google Gemini API key, read from the environment. Never hard-code this.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Scraper defaults ------------------------------------------------------

# Default search parameters (can be overridden via CLI in main.py).
# NOTE: LinkedIn only honors a fully-qualified location that includes the
# country (e.g. "Zurich, Switzerland"). A bare city like "Zurich" returns
# geo-defaulted / empty results.
DEFAULT_ROLE = "Solution Engineer"
DEFAULT_LOCATION = "Zurich, Switzerland"

# Human-like delay bounds (seconds) between actions to avoid bot detection.
MIN_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 5.0

# Maximum number of job cards to scrape per run.
MAX_JOBS = 25

# --- Analyzer defaults -----------------------------------------------------

# Gemini model used for structured job-description analysis.
# `gemini-3.1-flash-lite` is fast and has higher free-tier RPM limits.
GEMINI_MODEL = "gemini-3.1-flash-lite"

# Seconds to wait between consecutive Gemini requests. The free tier has a
# strict requests-per-minute (RPM) limit, so pausing between calls avoids
# `429 TooManyRequests` errors. The current free-tier quota is 15 RPM, so a
# 4.2-second pause stays just below that limit.
ANALYZER_DELAY_SECONDS = 4.2


def ensure_data_dir() -> Path:
    """Create the data directory if it does not already exist and return it."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def ensure_cv_dir() -> Path:
    """Create the private CV storage directory and return it."""
    CV_DIR.mkdir(parents=True, exist_ok=True)
    return CV_DIR
