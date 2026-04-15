"""
Reset episodes back to pending so they get re-scraped.
By default resets only episodes where no tracks were found (tracks=0).
Pass --all to reset every scraped episode.

Usage:
    python reset_scrape.py          # reset zero-track episodes only
    python reset_scrape.py --all    # reset all scraped episodes
"""

import sys
import database as db

db.init_db()

reset_all = "--all" in sys.argv

with db.get_connection() as conn:
    if reset_all:
        result = conn.execute(
            "UPDATE episodes SET scrape_status='pending', scrape_error=NULL "
            "WHERE scrape_status='done'"
        )
    else:
        result = conn.execute(
            """
            UPDATE episodes
            SET scrape_status='pending', scrape_error=NULL
            WHERE scrape_status='done'
              AND id NOT IN (SELECT DISTINCT episode_id FROM tracks)
            """
        )
    count = result.rowcount

print(f"Reset {count} episodes to pending.")
