"""
Configuration for the Communion After Dark archiver.

Tune DELAY_BETWEEN_REQUESTS and BATCH_SIZE to control how aggressively
the scraper hits the server. The defaults are intentionally conservative.

NAS / multi-machine setup
--------------------------
Set environment variables to redirect archive storage to a NAS mount or any
other location outside the repo.  Copy .env.example → .env and fill in your
paths, then `source .env` (Linux/macOS) or set them in your shell profile.

  CAD_ARCHIVE_DIR   Path where audio, artwork, and per-episode folders live.
  CAD_DATA_DIR      Path where cad_archive.db is stored.

If neither variable is set the paths default to archive/ and data/ inside
the repository root (good for local single-machine use).
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent          # repo root

# Allow overriding via environment variables for NAS / multi-machine setups.
ARCHIVE_DIR = Path(os.environ["CAD_ARCHIVE_DIR"]) \
              if "CAD_ARCHIVE_DIR" in os.environ \
              else BASE_DIR / "archive"

DATA_DIR    = Path(os.environ["CAD_DATA_DIR"]) \
              if "CAD_DATA_DIR" in os.environ \
              else BASE_DIR / "data"

DB_PATH     = DATA_DIR / "cad_archive.db"

# ---------------------------------------------------------------------------
# Network / rate-limiting
# ---------------------------------------------------------------------------

BASE_URL         = "https://www.communionafterdark.com"
RSS_URL          = "https://rss.buzzsprout.com/1609840.rss"
MIXCLOUD_PROFILE = "CommunionAfterDark"

# ntfy topic endpoint for push notifications. Set CAD_NTFY_URL in the cron
# environment to enable. Leave unset to disable notifications silently.
NTFY_URL = os.environ.get("CAD_NTFY_URL", "")

# Seconds to wait between every HTTP request (page fetches AND downloads).
# Increase this if you want to be even more conservative.
DELAY_BETWEEN_REQUESTS: float = 4.0

# Extra seconds to pause after every batch of episodes.
DELAY_BETWEEN_BATCHES: float = 30.0

# Number of episodes to process before taking the longer batch pause.
BATCH_SIZE: int = 10

# Maximum retries on transient errors (429 / 5xx).
MAX_RETRIES: int = 3

# Seconds to wait after a 429 Too Many Requests response.
RETRY_AFTER_429: float = 60.0

# HTTP request timeout in seconds.
REQUEST_TIMEOUT: int = 30

# User-Agent string — descriptive and honest so the site owner can identify
# and contact the archiver if they wish.
USER_AGENT = (
    "CAD-Personal-Archiver/1.0 "
    "(Non-commercial personal archive of Communion After Dark; "
    "https://www.communionafterdark.com)"
)

# ---------------------------------------------------------------------------
# Archive year pages — from the /archive-list page, 2026 has no link yet.
# ---------------------------------------------------------------------------

YEAR_ARCHIVE_URLS = {
    2025: "/2025-communion-after-dark-episodes",
    2024: "/2024-communion-after-dark-episodes",
    2023: "/2023-communion-after-dark-episodes",
    2022: "/2022-communion-after-dark-episodes",
    2021: "/2021-communion-after-dark-episodes",
    2020: "/2020-communion-after-dark-episodes",
    2019: "/2019-communion-after-dark-shows",
    2018: "/2018-communion-after-dark-shows",
    2017: "/2017communionafterdarkepisodes",
    2016: "/2016-communion-after-dark-episodes",
    2015: "/2015-communion-after-dark-episodes",
    2014: "/2014-communion-after-dark-episodes",
    2013: "/2013-communion-after-dark-archive",
    2012: "/2012-communion-after-dark-archive-list",
    2011: "/2011-communion-after-dark-episodes",
    2010: "/2010-communion-after-dark-episodes",
    2009: "/2009-communion-after-dark-episodes",
    2008: "/2008-communion-after-dark-episodes",
}

SPECIAL_ARCHIVE_URLS = {
    "2020-bonus":  "/2020-bonus-shows",
    "covers":      "/annual-covers-shows",
    "halloween":   "/halloween-special-editions",
    # Main listennow page — shows the most recent ~20 episodes regardless of year.
    # Used to discover new episodes before a year-archive page is created (e.g. 2026).
    "recent":      "/listennow",
}
