"""
SQLite database layer for the CAD archiver.

Tables
------
episodes
    One row per discovered episode. Tracks scrape state and download state
    independently so each can be retried without re-doing the other.

tracks
    One row per track in a tracklist. FK → episodes.id.

The database is the source of truth for "what have we done" — this makes
the entire pipeline safely resumable after interruption.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from config import DB_PATH


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS episodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Discovery
    year            INTEGER,
    category        TEXT,                      -- 'annual', 'bonus', 'covers', 'halloween'
    page_url        TEXT UNIQUE NOT NULL,      -- full Squarespace URL
    buzzsprout_id   INTEGER,                   -- extracted from audio URL

    -- Scraped metadata
    title           TEXT,
    pub_date        TEXT,                      -- ISO-8601 date string
    description     TEXT,
    artwork_url     TEXT,
    audio_url       TEXT,                      -- direct MP3 URL or Mixcloud page URL
    audio_source    TEXT,                      -- 'buzzsprout' | 'direct' | 'mixcloud'
    duration_sec    INTEGER,

    -- Local file paths (relative to ARCHIVE_DIR)
    audio_path      TEXT,
    artwork_path    TEXT,
    metadata_path   TEXT,

    -- State machine
    -- discovered → scraped → audio_downloaded → artwork_downloaded → tagged → done
    scrape_status   TEXT NOT NULL DEFAULT 'pending',   -- pending / done / error
    audio_status    TEXT NOT NULL DEFAULT 'pending',   -- pending / done / error / no_audio
    artwork_status  TEXT NOT NULL DEFAULT 'pending',
    tag_status      TEXT NOT NULL DEFAULT 'pending',
    scrape_error    TEXT,
    audio_error     TEXT,

    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tracks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    timestamp   TEXT,
    artist      TEXT,
    title       TEXT,
    album       TEXT,
    label       TEXT,
    country     TEXT,
    extra       TEXT    -- JSON blob for any additional fields
);

CREATE TABLE IF NOT EXISTS favorites (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id      INTEGER NOT NULL,
    position        INTEGER NOT NULL,
    -- Denormalized: duplicated from tracks/episodes so favorites survive
    -- a re-scrape that would DELETE FROM tracks for the episode.
    artist          TEXT,
    title           TEXT,        -- song title
    timestamp       TEXT,
    episode_title   TEXT,
    pub_date        TEXT,
    audio_path      TEXT,        -- relative path, same format as episodes.audio_path
    artwork_path    TEXT,
    favorited_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(episode_id, position)
);

CREATE INDEX IF NOT EXISTS idx_episodes_year          ON episodes(year);
CREATE INDEX IF NOT EXISTS idx_episodes_scrape_status ON episodes(scrape_status);
CREATE INDEX IF NOT EXISTS idx_episodes_audio_status  ON episodes(audio_status);
CREATE INDEX IF NOT EXISTS idx_tracks_episode         ON tracks(episode_id, position);
CREATE INDEX IF NOT EXISTS idx_favorites_episode      ON favorites(episode_id);
CREATE INDEX IF NOT EXISTS idx_favorites_date         ON favorites(favorited_at);
"""


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply incremental schema changes to existing databases."""
    migrations = [
        "ALTER TABLE episodes ADD COLUMN audio_source TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # Column already exists


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


# ---------------------------------------------------------------------------
# Episode helpers
# ---------------------------------------------------------------------------

def upsert_episode(page_url: str, year: Optional[int] = None,
                   category: str = "annual") -> int:
    """Insert episode if not present; return its id."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO episodes (page_url, year, category)
            VALUES (?, ?, ?)
            ON CONFLICT(page_url) DO NOTHING
            """,
            (page_url, year, category),
        )
        row = conn.execute(
            "SELECT id FROM episodes WHERE page_url = ?", (page_url,)
        ).fetchone()
        return row["id"]


def update_episode_metadata(episode_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = "datetime('now')"
    set_clause = ", ".join(
        f"{k} = datetime('now')" if v == "datetime('now')" else f"{k} = ?"
        for k, v in fields.items()
    )
    values = [v for v in fields.values() if v != "datetime('now')"]
    values.append(episode_id)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE episodes SET {set_clause} WHERE id = ?", values
        )


def set_scrape_done(episode_id: int, **metadata: Any) -> None:
    metadata["scrape_status"] = "done"
    update_episode_metadata(episode_id, **metadata)


def set_scrape_error(episode_id: int, error: str) -> None:
    update_episode_metadata(episode_id, scrape_status="error", scrape_error=error)


def set_audio_done(episode_id: int, audio_path: str) -> None:
    update_episode_metadata(episode_id, audio_status="done", audio_path=audio_path)


def set_audio_error(episode_id: int, error: str) -> None:
    update_episode_metadata(episode_id, audio_status="error", audio_error=error)


def set_audio_unavailable(episode_id: int) -> None:
    update_episode_metadata(episode_id, audio_status="no_audio")


def set_artwork_done(episode_id: int, artwork_path: str) -> None:
    update_episode_metadata(episode_id, artwork_status="done", artwork_path=artwork_path)


def set_tag_done(episode_id: int) -> None:
    update_episode_metadata(episode_id, tag_status="done")


def insert_tracks(episode_id: int, tracks: list[dict]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM tracks WHERE episode_id = ?", (episode_id,))
        conn.executemany(
            """
            INSERT INTO tracks
                (episode_id, position, timestamp, artist, title, album, label, country, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    episode_id,
                    t.get("position", i),
                    t.get("timestamp"),
                    t.get("artist"),
                    t.get("title"),
                    t.get("album"),
                    t.get("label"),
                    t.get("country"),
                    json.dumps(t.get("extra")) if t.get("extra") else None,
                )
                for i, t in enumerate(tracks, start=1)
            ],
        )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_pending_scrape(limit: int = 50) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, page_url, year, category
            FROM episodes
            WHERE scrape_status = 'pending'
            ORDER BY year DESC, id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_pending_audio(limit: int = 20) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, audio_url, title, pub_date, year, category
            FROM episodes
            WHERE audio_status = 'pending'
              AND audio_url IS NOT NULL
              AND scrape_status = 'done'
            ORDER BY year DESC, id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_pending_artwork(limit: int = 50) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, artwork_url, title, pub_date, year
            FROM episodes
            WHERE artwork_status = 'pending'
              AND artwork_url IS NOT NULL
              AND scrape_status = 'done'
            ORDER BY year DESC, id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_pending_tag(limit: int = 50) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT e.id, e.title, e.pub_date, e.year, e.description,
                   e.audio_path, e.artwork_path
            FROM episodes e
            WHERE e.tag_status = 'pending'
              AND e.audio_status = 'done'
              AND e.audio_path IS NOT NULL
            ORDER BY e.year DESC, e.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_tracks_for_episode(episode_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM tracks WHERE episode_id = ? ORDER BY position",
            (episode_id,),
        ).fetchall()


def stats() -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                                        AS total,
                SUM(scrape_status  = 'done')                   AS scraped,
                SUM(audio_status   = 'done')                   AS audio_done,
                SUM(audio_status   = 'no_audio')               AS no_audio,
                SUM(artwork_status = 'done')                   AS artwork_done,
                SUM(tag_status     = 'done')                   AS tagged,
                SUM(scrape_status  = 'error')                  AS scrape_errors,
                SUM(audio_status   = 'error')                  AS audio_errors
            FROM episodes
            """
        ).fetchone()
        return dict(row)
