"""
Communion After Dark — Archive API Server

Serves episode metadata, tracklists, audio streams, artwork, and favorites
from the SQLite archive database.  Designed to be consumed by the Android
and GTK4 players.

Environment variables (required):
    CAD_DB_PATH       — absolute path to cad.db
    CAD_ARCHIVE_ROOT  — directory that is the parent of archive/ and data/
                        (audio_path / artwork_path in the DB are relative to this)

Example:
    CAD_DB_PATH=/data/cad.db  CAD_ARCHIVE_ROOT=/nas  uvicorn main:app
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH       = Path(os.environ["CAD_DB_PATH"])
ARCHIVE_ROOT  = Path(os.environ["CAD_ARCHIVE_ROOT"])

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CAD Archive API",
    description="Communion After Dark personal archive",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # LAN-only service; tighten if ever exposed externally
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Years
# ---------------------------------------------------------------------------

@app.get("/api/years")
def list_years():
    """Years that have at least one episode, with counts."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT year,
                   COUNT(*)                      AS total,
                   SUM(audio_status = 'done')    AS with_audio,
                   SUM(audio_status = 'no_audio') AS no_audio
            FROM episodes
            WHERE year IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Episodes
# ---------------------------------------------------------------------------

@app.get("/api/episodes")
def list_episodes(
    year: Optional[int] = None,
    audio_only: bool = False,
    limit: int = 200,
    offset: int = 0,
):
    """List episodes, optionally filtered by year or restricted to those with audio."""
    filters = []
    params: list = []

    if year is not None:
        filters.append("e.year = ?")
        params.append(year)
    if audio_only:
        filters.append("e.audio_status = 'done' AND e.audio_path IS NOT NULL")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT e.id, e.title, e.pub_date, e.year, e.category,
                   e.audio_status, e.artwork_status, e.audio_source,
                   e.audio_path, e.artwork_path,
                   (SELECT COUNT(*) FROM tracks t WHERE t.episode_id = e.id) AS track_count
            FROM episodes e
            {where}
            ORDER BY e.pub_date DESC NULLS LAST, e.id DESC
            LIMIT ? OFFSET ?
        """, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/episodes/{episode_id}")
def get_episode(episode_id: int):
    """Full episode record."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Episode not found")
    return dict(row)


@app.get("/api/episodes/{episode_id}/tracks")
def get_tracks(episode_id: int):
    """Ordered tracklist for an episode."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tracks WHERE episode_id = ? ORDER BY position",
            (episode_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Audio streaming  (range-request aware for seeking in ExoPlayer / Media3)
# ---------------------------------------------------------------------------

@app.get("/api/episodes/{episode_id}/audio")
async def stream_audio(episode_id: int, request: Request):
    """
    Stream the episode audio.  Supports HTTP Range requests so Android
    Media3/ExoPlayer can seek without downloading the whole file first.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT audio_path FROM episodes WHERE id = ? AND audio_status = 'done'",
            (episode_id,),
        ).fetchone()

    if not row or not row["audio_path"]:
        raise HTTPException(404, "Audio not available for this episode")

    audio_file = ARCHIVE_ROOT / row["audio_path"].replace("\\", "/")
    if not audio_file.exists():
        raise HTTPException(404, "Audio file missing from archive")

    file_size = audio_file.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # Parse "bytes=start-end"
        try:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0])
            end   = int(byte_range[1]) if byte_range[1] else file_size - 1
        except (ValueError, IndexError):
            raise HTTPException(416, "Invalid Range header")

        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        with open(audio_file, "rb") as f:
            f.seek(start)
            data = f.read(chunk_size)

        return Response(
            content=data,
            status_code=206,
            media_type="audio/mpeg",
            headers={
                "Content-Range":  f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges":  "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    # No range header — serve the whole file
    return FileResponse(
        str(audio_file),
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"},
    )


# ---------------------------------------------------------------------------
# Artwork
# ---------------------------------------------------------------------------

@app.get("/api/episodes/{episode_id}/artwork")
def get_artwork(episode_id: int):
    """Episode artwork image."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT artwork_path FROM episodes WHERE id = ? AND artwork_status = 'done'",
            (episode_id,),
        ).fetchone()

    if not row or not row["artwork_path"]:
        raise HTTPException(404, "Artwork not available")

    artwork_file = ARCHIVE_ROOT / row["artwork_path"].replace("\\", "/")
    if not artwork_file.exists():
        raise HTTPException(404, "Artwork file missing from archive")

    suffix = artwork_file.suffix.lower()
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png", "webp": "image/webp"}.get(suffix.lstrip("."), "image/jpeg")
    return FileResponse(str(artwork_file), media_type=media_type)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.get("/api/search")
def search(q: str, limit: int = 50):
    """
    Full-text search across track artist, title, and album.
    Only returns tracks from episodes with downloaded audio.
    """
    if len(q.strip()) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")

    pattern = f"%{q}%"
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.id, t.episode_id, t.position, t.timestamp,
                   t.artist, t.title, t.album, t.label, t.country,
                   e.title  AS episode_title,
                   e.pub_date, e.year,
                   e.audio_path, e.artwork_path
            FROM tracks t
            JOIN episodes e ON e.id = t.episode_id
            WHERE e.audio_status = 'done'
              AND (t.artist LIKE ? OR t.title LIKE ? OR t.album LIKE ?)
            ORDER BY e.pub_date DESC
            LIMIT ?
        """, (pattern, pattern, pattern, limit)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

@app.get("/api/favorites")
def list_favorites():
    """All favorited tracks, newest first."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM favorites ORDER BY favorited_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.put("/api/favorites/{episode_id}/{position}")
def toggle_favorite(episode_id: int, position: int):
    """Add or remove a track from favorites.  Returns new favorited state."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM favorites WHERE episode_id = ? AND position = ?",
            (episode_id, position),
        ).fetchone()

        if existing:
            conn.execute(
                "DELETE FROM favorites WHERE episode_id = ? AND position = ?",
                (episode_id, position),
            )
            return {"favorited": False}

        # Denormalize track + episode info so favorites survive re-scrapes
        row = conn.execute("""
            SELECT t.artist, t.title, t.timestamp,
                   e.title AS episode_title, e.pub_date,
                   e.audio_path, e.artwork_path
            FROM tracks t
            JOIN episodes e ON e.id = t.episode_id
            WHERE t.episode_id = ? AND t.position = ?
        """, (episode_id, position)).fetchone()

        if not row:
            raise HTTPException(404, "Track not found")

        conn.execute("""
            INSERT INTO favorites
                (episode_id, position, artist, title, timestamp,
                 episode_title, pub_date, audio_path, artwork_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            episode_id, position,
            row["artist"], row["title"], row["timestamp"],
            row["episode_title"], row["pub_date"],
            row["audio_path"], row["artwork_path"],
        ))
        return {"favorited": True}


# ---------------------------------------------------------------------------
# New-episode poll  (consumed by Android NewEpisodeCheckWorker)
# ---------------------------------------------------------------------------

@app.get("/cad-new-episode/json")
def new_episode_poll(since: int = 0):
    """
    Returns a JSON line with a "message" key if any episode with audio was
    published after *since* (Unix timestamp).  Returns an empty body when
    there is nothing new so the Android worker fires no notification.
    """
    with get_db() as conn:
        row = conn.execute("""
            SELECT title FROM episodes
            WHERE pub_date > date(?, 'unixepoch')
              AND audio_status = 'done'
            ORDER BY pub_date DESC
            LIMIT 1
        """, (since,)).fetchone()

    if not row:
        return Response(content="", media_type="text/plain")

    import json as _json
    return Response(
        content=_json.dumps({"message": f"New episode: {row['title']}"}),
        media_type="application/json",
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    return {"status": "ok", "episodes": count}
