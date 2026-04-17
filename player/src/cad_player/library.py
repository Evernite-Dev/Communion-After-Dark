"""
Library model: reads from the SQLite archive database or falls back to
scanning metadata.json files.  Provides a simple read-only API for the UI.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Track:
    position: int
    timestamp: str = ""
    artist: str = ""
    title: str = ""
    album: str = ""
    label: str = ""
    country: str = ""


@dataclass
class TrackResult:
    """A single track match from a search, with its parent episode attached."""
    track: "Track"
    episode: "Episode"


@dataclass
class Episode:
    id: int
    title: str
    pub_date: str
    year: int | None
    description: str
    audio_path: str       # absolute path
    artwork_path: str     # absolute path, may be ""
    tracklist: list[Track] = field(default_factory=list)
    duration_sec: int = 0
    page_url: str = ""

    @property
    def display_title(self) -> str:
        return self.title or Path(self.audio_path).stem

    @property
    def artwork_exists(self) -> bool:
        return bool(self.artwork_path) and Path(self.artwork_path).exists()


# ---------------------------------------------------------------------------
# Library loader
# ---------------------------------------------------------------------------

class Library:
    def __init__(self, archive_root: str | Path, db_path: str | Path | None = None):
        self.archive_root = Path(archive_root)
        self.db_path = Path(db_path) if db_path else None
        self._episodes: list[Episode] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load all episodes. Prefers DB if available, else scans JSON."""
        if self.db_path and self.db_path.exists():
            self._load_from_db()
        else:
            self._load_from_json()

    @property
    def episodes(self) -> list[Episode]:
        return self._episodes

    def years(self) -> list[int]:
        return sorted({e.year for e in self._episodes if e.year}, reverse=True)

    def episodes_for_year(self, year: int) -> list[Episode]:
        return sorted(
            [e for e in self._episodes if e.year == year],
            key=lambda e: e.pub_date or "",
            reverse=True,
        )

    def episode_by_id(self, episode_id: int) -> Episode | None:
        for ep in self._episodes:
            if ep.id == episode_id:
                return ep
        return None

    def search(self, query: str) -> list[Episode]:
        q = query.lower()
        results = []
        for ep in self._episodes:
            if (q in ep.display_title.lower()
                    or q in ep.description.lower()
                    or any(q in t.artist.lower() or q in t.title.lower()
                           for t in ep.tracklist)):
                results.append(ep)
        return results

    def search_tracks(self, query: str) -> list[TrackResult]:
        """Return individual track matches (artist or title contains query)."""
        q = query.lower()
        results = []
        for ep in self._episodes:
            for track in ep.tracklist:
                if q in track.artist.lower() or q in track.title.lower():
                    results.append(TrackResult(track=track, episode=ep))
        return results

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _load_from_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT id, title, pub_date, year, description,
                   audio_path, artwork_path, duration_sec, page_url
            FROM episodes
            WHERE audio_status = 'done' AND audio_path IS NOT NULL
            ORDER BY pub_date DESC
            """
        ).fetchall()

        episodes: list[Episode] = []
        for row in rows:
            audio_abs   = str(self.archive_root.parent / row["audio_path"])
            artwork_abs = str(self.archive_root.parent / row["artwork_path"]) \
                          if row["artwork_path"] else ""

            tracks_rows = conn.execute(
                "SELECT * FROM tracks WHERE episode_id = ? ORDER BY position",
                (row["id"],),
            ).fetchall()
            tracks = [
                Track(
                    position=t["position"],
                    timestamp=t["timestamp"] or "",
                    artist=t["artist"] or "",
                    title=t["title"] or "",
                    album=t["album"] or "",
                    label=t["label"] or "",
                    country=t["country"] or "",
                )
                for t in tracks_rows
            ]

            episodes.append(Episode(
                id=row["id"],
                title=row["title"] or "",
                pub_date=row["pub_date"] or "",
                year=row["year"],
                description=row["description"] or "",
                audio_path=audio_abs,
                artwork_path=artwork_abs,
                tracklist=tracks,
                duration_sec=row["duration_sec"] or 0,
                page_url=row["page_url"] or "",
            ))

        conn.close()
        self._episodes = episodes

    def _load_from_json(self) -> None:
        """Fallback: scan archive dir for metadata.json files."""
        episodes: list[Episode] = []
        for meta_file in sorted(self.archive_root.rglob("metadata.json"), reverse=True):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            ep_dir = meta_file.parent
            audio_path = str(ep_dir / "audio.mp3") if (ep_dir / "audio.mp3").exists() else ""
            if not audio_path:
                continue

            # Find artwork
            artwork_path = ""
            for ext in ("jpg", "jpeg", "png", "webp"):
                candidate = ep_dir / f"artwork.{ext}"
                if candidate.exists():
                    artwork_path = str(candidate)
                    break

            tracks = [
                Track(
                    position=t.get("position", i),
                    timestamp=t.get("timestamp", ""),
                    artist=t.get("artist", ""),
                    title=t.get("title", ""),
                    album=t.get("album", ""),
                    label=t.get("label", ""),
                    country=t.get("country", ""),
                )
                for i, t in enumerate(data.get("tracklist", []), start=1)
            ]

            year_str = ep_dir.parent.name
            year = int(year_str) if year_str.isdigit() else None

            episodes.append(Episode(
                id=data.get("id", 0),
                title=data.get("title", ""),
                pub_date=data.get("pub_date", ""),
                year=year,
                description=data.get("description", ""),
                audio_path=audio_path,
                artwork_path=artwork_path,
                tracklist=tracks,
                duration_sec=data.get("duration_sec", 0),
                page_url=data.get("page_url", ""),
            ))

        self._episodes = episodes
