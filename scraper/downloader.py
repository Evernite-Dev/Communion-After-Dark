"""
Phase 3 — File downloader

Downloads audio (MP3) and artwork (images) for scraped episodes.
Saves files under ARCHIVE_DIR/<year>/<safe-slug>/ and records the paths in DB.

File layout per episode:
    archive/
        2025/
            2025-12-29_best-of-2025/
                audio.mp3
                artwork.jpg
                metadata.json
"""

import json
import logging
import re
import time
from pathlib import Path

import database as db
from config import ARCHIVE_DIR, BATCH_SIZE, DELAY_BETWEEN_BATCHES
from http_client import download_file

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_DASH   = re.compile(r"-{2,}")
_MULTI_SPACE  = re.compile(r"\s+")


def _safe_name(text: str, max_len: int = 60) -> str:
    text = _MULTI_SPACE.sub(" ", text).strip()
    text = _UNSAFE_CHARS.sub("", text)
    text = text.replace(" ", "-").lower()
    text = _MULTI_DASH.sub("-", text)
    return text[:max_len].strip("-")


def episode_dir(year: int | None, pub_date: str | None, title: str | None) -> Path:
    year_str = str(year) if year else "unknown"
    date_str = (pub_date or "")[:10]  # YYYY-MM-DD
    slug = _safe_name(title or "untitled")
    folder_name = f"{date_str}_{slug}" if date_str else slug
    return ARCHIVE_DIR / year_str / folder_name


# ---------------------------------------------------------------------------
# metadata.json writer
# ---------------------------------------------------------------------------

def write_metadata_json(ep_dir: Path, episode_id: int, row: dict) -> Path:
    """Write a metadata.json file into ep_dir, including the tracklist."""
    tracks = [dict(t) for t in db.get_tracks_for_episode(episode_id)]
    payload = {
        "id":          episode_id,
        "title":       row.get("title"),
        "pub_date":    row.get("pub_date"),
        "description": row.get("description"),
        "artwork_url": row.get("artwork_url"),
        "audio_url":   row.get("audio_url"),
        "duration_sec":row.get("duration_sec"),
        "year":        row.get("year"),
        "category":    row.get("category"),
        "page_url":    row.get("page_url"),
        "tracklist":   tracks,
    }
    dest = ep_dir / "metadata.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return dest


# ---------------------------------------------------------------------------
# Audio download
# ---------------------------------------------------------------------------

def download_audio_batch(batch_size: int = BATCH_SIZE) -> int:
    """Download audio for up to batch_size episodes. Returns success count."""
    pending = db.get_pending_audio(limit=batch_size)
    if not pending:
        log.info("No pending audio downloads.")
        return 0

    success = 0
    for i, row in enumerate(pending, start=1):
        ep_id   = row["id"]
        url     = row["audio_url"]
        title   = row["title"] or f"episode-{ep_id}"
        year    = row["year"]
        pub_date= row["pub_date"]

        ep_dir = episode_dir(year, pub_date, title)
        dest   = ep_dir / "audio.mp3"

        if dest.exists():
            log.info("Audio already present: %s — marking done", dest)
            db.set_audio_done(ep_id, str(dest.relative_to(ARCHIVE_DIR.parent)))
            success += 1
            continue

        try:
            download_file(url, dest)
            rel = str(dest.relative_to(ARCHIVE_DIR.parent))
            db.set_audio_done(ep_id, rel)
            # Also write/update metadata.json now that we have a local dir
            _write_meta_if_needed(ep_dir, ep_id, row)
            success += 1
        except Exception as exc:
            log.error("Failed audio download for ep#%d: %s", ep_id, exc)
            db.set_audio_error(ep_id, str(exc))

        if i % BATCH_SIZE == 0 and i < len(pending):
            log.info("Batch pause (%.0fs)…", DELAY_BETWEEN_BATCHES)
            time.sleep(DELAY_BETWEEN_BATCHES)

    return success


# ---------------------------------------------------------------------------
# Artwork download
# ---------------------------------------------------------------------------

_IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif)(?:\?.*)?$", re.IGNORECASE)


def _artwork_extension(url: str) -> str:
    m = _IMG_EXT.search(url)
    if m:
        ext = m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext
    return "jpg"


def download_artwork_batch(batch_size: int = BATCH_SIZE * 3) -> int:
    """Download artwork for up to batch_size episodes. Returns success count."""
    pending = db.get_pending_artwork(limit=batch_size)
    if not pending:
        log.info("No pending artwork downloads.")
        return 0

    success = 0
    for row in pending:
        ep_id    = row["id"]
        url      = row["artwork_url"]
        title    = row["title"] or f"episode-{ep_id}"
        year     = row["year"]
        pub_date = row["pub_date"]
        ext      = _artwork_extension(url)

        ep_dir = episode_dir(year, pub_date, title)
        dest   = ep_dir / f"artwork.{ext}"

        if dest.exists():
            db.set_artwork_done(ep_id, str(dest.relative_to(ARCHIVE_DIR.parent)))
            success += 1
            continue

        try:
            download_file(url, dest)
            db.set_artwork_done(ep_id, str(dest.relative_to(ARCHIVE_DIR.parent)))
            success += 1
        except Exception as exc:
            log.error("Failed artwork download for ep#%d: %s", ep_id, exc)
            # Non-fatal — don't set error, just leave as pending for retry

    return success


# ---------------------------------------------------------------------------
# metadata.json helper (called after audio download to ensure dir exists)
# ---------------------------------------------------------------------------

def _write_meta_if_needed(ep_dir: Path, ep_id: int, row) -> None:
    meta_path = ep_dir / "metadata.json"
    if not meta_path.exists():
        write_metadata_json(ep_dir, ep_id, dict(row))
        db.update_episode_metadata(ep_id, metadata_path=str(meta_path.relative_to(ARCHIVE_DIR.parent)))


def write_all_metadata_json() -> int:
    """
    (Re)writes metadata.json for every episode whose audio has been downloaded.
    Useful for refreshing after tracklists are updated.
    """
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, pub_date, description, artwork_url, audio_url,
                   duration_sec, year, category, page_url, audio_path
            FROM episodes
            WHERE audio_status = 'done' AND audio_path IS NOT NULL
            """
        ).fetchall()

    count = 0
    for row in rows:
        row = dict(row)
        ep_dir = ARCHIVE_DIR.parent / Path(row["audio_path"]).parent
        write_metadata_json(ep_dir, row["id"], row)
        db.update_episode_metadata(
            row["id"],
            metadata_path=str((ep_dir / "metadata.json").relative_to(ARCHIVE_DIR.parent)),
        )
        count += 1
    return count
