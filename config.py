"""Central configuration. Secrets come from environment variables / .env only."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Database -------------------------------------------------------------
DB_PATH = Path(os.getenv("CRICBUZZ_DB_PATH", BASE_DIR / "data" / "cricbuzz.db"))
SCHEMA_FILE = BASE_DIR / "sql" / "schema.sql"

# --- Cricbuzz API (RapidAPI) ---------------------------------------------
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "cricbuzz-cricket.p.rapidapi.com")
API_BASE_URL = f"https://{RAPIDAPI_HOST}"
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "10"))
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))

# Link shown on the Home page (e.g. your GitHub repo / README URL)
DOCS_URL = os.getenv("DOCS_URL", "").strip()

SAMPLE_LIVE_FILE = BASE_DIR / "data" / "sample_live.json"
SAMPLE_TOPSTATS_FILE = BASE_DIR / "data" / "sample_topstats.json"

FORMATS = ("Test", "ODI", "T20I")
PLAYING_ROLES = ("Batsman", "Bowler", "All-rounder", "Wicket-keeper")


def api_configured() -> bool:
    """True when a RapidAPI key is present."""
    return bool(RAPIDAPI_KEY.strip())
