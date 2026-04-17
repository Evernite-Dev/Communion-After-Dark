"""
Favorites persistence for the CAD player.

Favorites are individual tracks (not whole episodes) that the user has
heart-toggled while browsing the tracklist.

Storage backends
----------------
SQLite (primary)
    Uses the same cad_archive.db the scraper creates.  The favorites table
    is created here with CREATE TABLE IF NOT EXISTS, so this module works
    even when the scraper hasn't run the new schema yet.

JSON sidecar (fallback)
    When no database is available (first run, archive still being scraped),
    favorites are persisted to data/favorites.json next to the archive dir.

Denormalization rationale
-------------------------
The favorites table copies artist/title/timestamp/episode_title/paths out
of the tracks + episodes tables.  This means favorites survive a track
re-scrape: the scraper does DELETE FROM tracks WHERE episode_id = ? before
re-inserting, which would otherwise cascade and silently erase saved favorites.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema (self-contained — no dependency on scraper/database.py)
# ---------------------------------------------------------------------------

_FAVORITES_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS favorites (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id      INTEGER NOT NULL,
    position        INTEGER NOT NULL,
    artist          TEXT,
    title           TEXT,
    timestamp       TEXT,
    episode_title   TEXT,
    pub_date        TEXT,
    audio_path      TEXT,
    artwork_path    TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    favorited_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(episode_id, position)
);

CREATE INDEX IF NOT EXISTS idx_favorites_episode   ON favorites(episode_id);
CREATE INDEX IF NOT EXISTS idx_favorites_date      ON favorites(favorited_at);
CREATE INDEX IF NOT EXISTS idx_favorites_sort      ON favorites(sort_order);
"""


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class Favorite:
    episode_id:    int
    position:      int
    artist:        str
    title:         str    # song title
    timestamp:     str
    episode_title: str
    pub_date:      str
    audio_path:    str    # absolute path
    artwork_path:  str    # absolute path, may be ""
    favorited_at:  str = ""

    @property
    def display_artist_title(self) -> str:
        if self.artist and self.title:
            return f"{self.artist} — {self.title}"
        return self.artist or self.title or "Unknown track"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class FavoritesStore:
    """
    Manages favorite track persistence.
    One instance lives for the lifetime of the player window.
    Not thread-safe (single SQLite connection on the main thread).
    """

    def __init__(self, db_path: Path | None, archive_root: Path | None = None) -> None:
        self._archive_root = archive_root
        self._conn: sqlite3.Connection | None = None
        self._json_path: Path | None = None

        if db_path and db_path.exists():
            self._conn = sqlite3.connect(str(db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_FAVORITES_DDL)
            # Migrate: add sort_order column to existing databases
            try:
                self._conn.execute(
                    "ALTER TABLE favorites ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
            self._conn.commit()
            self._ensure_sort_order()
        else:
            # Fallback: JSON sidecar file
            if archive_root:
                self._json_path = archive_root.parent / "data" / "favorites.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def toggle(self, episode_id: int, position: int, **fields) -> bool:
        """
        Toggle the favorite state for (episode_id, position).

        Accepted keyword arguments (all optional but strongly recommended):
            artist, title, timestamp, episode_title, pub_date,
            audio_path, artwork_path

        Returns True if the track is now a favorite, False if it was removed.
        """
        if self._conn:
            return self._db_toggle(episode_id, position, **fields)
        return self._json_toggle(episode_id, position, **fields)

    def is_favorite(self, episode_id: int, position: int) -> bool:
        if self._conn:
            row = self._conn.execute(
                "SELECT 1 FROM favorites WHERE episode_id=? AND position=?",
                (episode_id, position),
            ).fetchone()
            return row is not None
        return self._json_is_favorite(episode_id, position)

    def episode_favorite_positions(self, episode_id: int) -> set[int]:
        """Return the set of favorited track positions for a single episode."""
        if self._conn:
            rows = self._conn.execute(
                "SELECT position FROM favorites WHERE episode_id=?", (episode_id,)
            ).fetchall()
            return {r["position"] for r in rows}
        return self._json_episode_positions(episode_id)

    def get_all(self) -> list[Favorite]:
        """Return all favorites in user-defined order (sort_order ASC)."""
        if self._conn:
            rows = self._conn.execute(
                "SELECT * FROM favorites ORDER BY sort_order ASC, favorited_at DESC"
            ).fetchall()
            return [self._row_to_fav(r) for r in rows]
        return self._json_get_all()

    def reorder(self, from_idx: int, to_idx: int) -> None:
        """Move the favorite at from_idx to to_idx (0-based, from get_all order)."""
        if not self._conn or from_idx == to_idx:
            return
        rows = self._conn.execute(
            "SELECT id FROM favorites ORDER BY sort_order ASC, favorited_at DESC"
        ).fetchall()
        if from_idx < 0 or from_idx >= len(rows) or to_idx < 0 or to_idx >= len(rows):
            return
        ids = [r["id"] for r in rows]
        item = ids.pop(from_idx)
        ids.insert(to_idx, item)
        for i, id_ in enumerate(ids):
            self._conn.execute(
                "UPDATE favorites SET sort_order = ? WHERE id = ?", (i, id_)
            )
        self._conn.commit()

    def count(self) -> int:
        if self._conn:
            return self._conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
        return len(self._json_load())

    # ------------------------------------------------------------------
    # SQLite backend
    # ------------------------------------------------------------------

    def _ensure_sort_order(self) -> None:
        """Assign sequential sort_order to existing rows that are all 0 (first migration)."""
        total = self._conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
        if total <= 1:
            return
        unset = self._conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE sort_order = 0"
        ).fetchone()[0]
        if unset == total:
            # All rows uninitialized — number them by favorited_at DESC
            rows = self._conn.execute(
                "SELECT id FROM favorites ORDER BY favorited_at DESC"
            ).fetchall()
            for i, row in enumerate(rows):
                self._conn.execute(
                    "UPDATE favorites SET sort_order = ? WHERE id = ?", (i, row["id"])
                )
            self._conn.commit()

    def _db_toggle(self, episode_id: int, position: int, **fields) -> bool:
        existing = self._conn.execute(
            "SELECT id FROM favorites WHERE episode_id=? AND position=?",
            (episode_id, position),
        ).fetchone()

        if existing:
            self._conn.execute(
                "DELETE FROM favorites WHERE episode_id=? AND position=?",
                (episode_id, position),
            )
            self._conn.commit()
            return False

        # Place new favorites at the end of the user-defined order
        max_order = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM favorites"
        ).fetchone()[0]
        self._conn.execute(
            """
            INSERT INTO favorites
                (episode_id, position, artist, title, timestamp,
                 episode_title, pub_date, audio_path, artwork_path, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode_id, position,
                fields.get("artist", ""),
                fields.get("title", ""),
                fields.get("timestamp", ""),
                fields.get("episode_title", ""),
                fields.get("pub_date", ""),
                fields.get("audio_path", ""),
                fields.get("artwork_path", ""),
                max_order + 1,
            ),
        )
        self._conn.commit()
        return True

    def _row_to_fav(self, row: sqlite3.Row) -> Favorite:
        return Favorite(
            episode_id=row["episode_id"],
            position=row["position"],
            artist=row["artist"] or "",
            title=row["title"] or "",
            timestamp=row["timestamp"] or "",
            episode_title=row["episode_title"] or "",
            pub_date=row["pub_date"] or "",
            audio_path=self._abs(row["audio_path"] or ""),
            artwork_path=self._abs(row["artwork_path"] or ""),
            favorited_at=row["favorited_at"] or "",
        )

    def _abs(self, rel: str) -> str:
        """Convert a relative archive path to an absolute path."""
        if not rel or Path(rel).is_absolute():
            return rel
        if self._archive_root:
            return str(self._archive_root.parent / rel)
        return rel

    # ------------------------------------------------------------------
    # JSON fallback backend
    # ------------------------------------------------------------------

    def _json_load(self) -> list[dict]:
        if self._json_path and self._json_path.exists():
            try:
                return json.loads(self._json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _json_save(self, data: list[dict]) -> None:
        if not self._json_path:
            return
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        self._json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _key(episode_id: int, position: int) -> str:
        return f"{episode_id}:{position}"

    def _json_toggle(self, episode_id: int, position: int, **fields) -> bool:
        data = self._json_load()
        key = self._key(episode_id, position)
        idx = next(
            (i for i, f in enumerate(data)
             if self._key(f["episode_id"], f["position"]) == key),
            -1,
        )
        if idx >= 0:
            data.pop(idx)
            self._json_save(data)
            return False
        data.insert(0, {"episode_id": episode_id, "position": position, **fields})
        self._json_save(data)
        return True

    def _json_is_favorite(self, episode_id: int, position: int) -> bool:
        key = self._key(episode_id, position)
        return any(
            self._key(f["episode_id"], f["position"]) == key
            for f in self._json_load()
        )

    def _json_episode_positions(self, episode_id: int) -> set[int]:
        return {
            f["position"] for f in self._json_load()
            if f["episode_id"] == episode_id
        }

    def _json_get_all(self) -> list[Favorite]:
        return [
            Favorite(
                episode_id=f["episode_id"],
                position=f["position"],
                artist=f.get("artist", ""),
                title=f.get("title", ""),
                timestamp=f.get("timestamp", ""),
                episode_title=f.get("episode_title", ""),
                pub_date=f.get("pub_date", ""),
                audio_path=self._abs(f.get("audio_path", "")),
                artwork_path=self._abs(f.get("artwork_path", "")),
                favorited_at=f.get("favorited_at", ""),
            )
            for f in self._json_load()
        ]
