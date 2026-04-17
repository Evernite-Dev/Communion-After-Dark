#!/usr/bin/env python3
"""
weekly_update.py — Communion After Dark automated new-episode watcher
======================================================================

What it does
------------
Runs the full archiving pipeline (RSS discover → scrape → download audio →
download artwork → ID3 tag) once per invocation.  The script is idempotent:
if this week's episode is already captured it exits immediately without doing
any work.

Scheduling strategy
-------------------
Configure cron to fire every 4 hours on Monday.  The script exits as soon as
the new episode is captured, so later invocations that day become no-ops.

  Cron line (edit with `crontab -e` on the NAS):

      0 0,4,8,12,16,20 * * 1  /path/to/scraper/.venv/bin/python \
          /path/to/scraper/weekly_update.py \
          >> /path/to/data/weekly_update.log 2>&1

  Synology Task Scheduler alternative:
      Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script
      Schedule: Run on the following days → Monday
      Frequency: Every 4 hours
      Command: /path/to/scraper/.venv/bin/python /path/to/scraper/weekly_update.py

One-time NAS setup (via SSH)
----------------------------
  cd /path/to/scraper
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt

  # Add to ~/.profile or the cron environment block:
  export CAD_DATA_DIR=/volume1/path/to/data
  export CAD_ARCHIVE_DIR=/volume1/path/to/

  # Test run:
  .venv/bin/python weekly_update.py
"""

import logging
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

# Make the scraper package importable when invoked directly
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_PATH
import database as db
import crawler
import extractor
import downloader
import tagger

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Log file lives next to the database so it is easy to find on the NAS.
_log_file = Path(DB_PATH).parent / "weekly_update.log"
_log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _this_weeks_monday() -> str:
    """Return the ISO-8601 date of the Monday of the current week."""
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def _episode_captured_this_week() -> bool:
    """
    Return True if at least one episode whose pub_date falls on or after this
    Monday already has its audio file downloaded.
    """
    monday = _this_weeks_monday()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM episodes "
            "WHERE pub_date >= ? AND audio_status = 'done'",
            (monday,),
        ).fetchone()[0]
    finally:
        conn.close()
    return count > 0


def _reset_audio_errors() -> int:
    """
    Reset any episodes stuck in audio_status='error' back to 'pending' so
    they are retried this pass.  Returns number of rows reset.
    """
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "UPDATE episodes SET audio_status = 'pending', audio_error = NULL "
            "WHERE audio_status = 'error'"
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _run_pipeline() -> dict:
    """
    One full pass of the pipeline.  Batch sizes are intentionally small for a
    weekly new-episode run — there is only one new episode to process.
    Returns a dict of counts for logging.
    """
    log.info("Step 1/4  RSS + listing-page discovery")
    discovered_rss = crawler.crawl_rss()
    log.info(f"          {discovered_rss} episode(s) from RSS")
    # Also crawl /listennow and the current year's archive page.
    # This covers 2026+ episodes that no longer appear in the Buzzsprout RSS feed.
    discovered_listing = crawler.crawl_year_pages(years=[date.today().year])
    log.info(f"          {discovered_listing} episode(s) from listing pages")
    discovered = discovered_rss + discovered_listing

    log.info("Step 2/4  Scraping metadata")
    scraped = extractor.run_scrape_batch(batch_size=5)
    log.info(f"          {scraped} episode(s) scraped")

    log.info("Step 3/4  Downloading audio")
    reset = _reset_audio_errors()
    if reset:
        log.info(f"          {reset} error row(s) reset to pending for retry")
    audio = downloader.download_audio_batch(batch_size=5)
    log.info(f"          {audio} audio file(s) downloaded")

    log.info("Step 4/4  Artwork + ID3 tagging")
    artwork = downloader.download_artwork_batch(batch_size=10)
    tagged = tagger.run_tag_batch(batch_size=10)
    log.info(f"          {artwork} artwork file(s),  {tagged} file(s) tagged")

    return {
        "discovered": discovered,
        "scraped": scraped,
        "audio": audio,
        "artwork": artwork,
        "tagged": tagged,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 60)
    log.info(f"Weekly update start  (week of {_this_weeks_monday()})")

    db.init_db()

    if _episode_captured_this_week():
        log.info("This week's episode is already captured — nothing to do.")
        log.info("=" * 60)
        return

    log.info("No captured episode found for this week — running pipeline…")
    counts = _run_pipeline()

    if _episode_captured_this_week():
        log.info(
            "SUCCESS — new episode captured.  "
            f"discovered={counts['discovered']}  "
            f"scraped={counts['scraped']}  "
            f"audio={counts['audio']}  "
            f"tagged={counts['tagged']}"
        )
    else:
        log.info(
            "Episode not yet available after this pass.  "
            "Cron will retry in 4 hours."
        )

    log.info("=" * 60)


if __name__ == "__main__":
    main()
