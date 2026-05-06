"""Central configuration for all ETL modules.

Every other ETL module imports paths and constants from here.
No hardcoded paths elsewhere.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = DATA_DIR / "static"
DAILY_DIR = DATA_DIR / "daily"
PREV_DIR = DATA_DIR / "prev"

ROSTER_PDF = STATIC_DIR / "Club_Roster_Profiles_Feb2026.pdf"
ROSTER_CACHE = STATIC_DIR / "roster_cache.json"

# ── Scraping constants ─────────────────────────────────────────
DELAY: dict[str, float] = {
    "fotmob.com": 2.0,
    "data.fotmob.com": 2.0,
    "sofascore.com": 2.0,
    "mlssoccer.com": 3.0,
    "capology.com": 2.0,
    "transfermarkt.us": 3.0,
}

MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ── Season constants ───────────────────────────────────────────
SEASON = "2026"
MLS_LEAGUE_ID_FOTMOB = 130
MLS_TOURNAMENT_ID_SOFASCORE = 242
DP_SALARY_THRESHOLD = 1_680_000  # 2026 DP threshold in USD

# ── Capology ──────────────────────────────────────────────────
CAPOLOGY_MLS_URL = "https://www.capology.com/us/mls/salaries/"
