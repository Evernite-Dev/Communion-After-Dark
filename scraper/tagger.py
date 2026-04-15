"""
Phase 4 — ID3 tagger

Embeds metadata into downloaded MP3 files using ID3v2.4 tags (via mutagen).

Tags written:
  TIT2  — episode title
  TPE1  — artist / DJ names ("DJs Paradise, Winters and Gold")
  TALB  — album ("Communion After Dark")
  TDRC  — recording year
  TCON  — genre ("Electronic")
  COMM  — full episode description
  TRCK  — track number (episode number if derivable)
  APIC  — embedded artwork (if artwork file is present)
  TXXX:CADTracklist — JSON-encoded tracklist (custom frame)
  TXXX:CADPageURL  — original Squarespace episode URL
"""

import json
import logging
from pathlib import Path

from mutagen.id3 import (
    ID3,
    ID3NoHeaderError,
    TIT2,
    TPE1,
    TALB,
    TDRC,
    TCON,
    COMM,
    TRCK,
    APIC,
    TXXX,
)
from mutagen.mp3 import MP3

import database as db
from config import ARCHIVE_DIR

log = logging.getLogger(__name__)

PODCAST_ARTIST = "Communion After Dark (DJs Paradise, Winters & Gold)"
PODCAST_ALBUM  = "Communion After Dark"
GENRE          = "Electronic"


def _load_artwork_bytes(artwork_path: str | None) -> bytes | None:
    if not artwork_path:
        return None
    p = ARCHIVE_DIR.parent / artwork_path
    if p.exists():
        return p.read_bytes()
    return None


def _mime_from_path(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def tag_episode(episode_id: int) -> bool:
    """
    Read metadata from DB, embed tags into the episode's MP3 file.
    Returns True on success.
    """
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT e.id, e.title, e.pub_date, e.year, e.description,
                   e.audio_path, e.artwork_path, e.page_url
            FROM episodes e
            WHERE e.id = ?
            """,
            (episode_id,),
        ).fetchone()

    if not row:
        log.error("Episode #%d not found in DB", episode_id)
        return False

    audio_path = row["audio_path"]
    if not audio_path:
        log.warning("Episode #%d has no audio_path", episode_id)
        return False

    mp3_file = ARCHIVE_DIR.parent / audio_path
    if not mp3_file.exists():
        log.error("MP3 not found: %s", mp3_file)
        return False

    # Load (or create) ID3 tags
    try:
        tags = ID3(str(mp3_file))
    except ID3NoHeaderError:
        tags = ID3()

    # Clear any stale tags we manage
    for key in ["TIT2", "TPE1", "TALB", "TDRC", "TCON", "COMM::eng", "TRCK", "APIC:"]:
        tags.delall(key)

    # Basic tags
    if row["title"]:
        tags["TIT2"] = TIT2(encoding=3, text=row["title"])
    tags["TPE1"] = TPE1(encoding=3, text=PODCAST_ARTIST)
    tags["TALB"] = TALB(encoding=3, text=PODCAST_ALBUM)
    tags["TCON"] = TCON(encoding=3, text=GENRE)

    if row["pub_date"]:
        year = row["pub_date"][:4]
        tags["TDRC"] = TDRC(encoding=3, text=year)

    if row["description"]:
        tags["COMM:eng"] = COMM(encoding=3, lang="eng", desc="", text=row["description"])

    # Custom frames
    if row["page_url"]:
        tags.delall("TXXX:CADPageURL")
        tags["TXXX:CADPageURL"] = TXXX(encoding=3, desc="CADPageURL", text=row["page_url"])

    tracks = db.get_tracks_for_episode(episode_id)
    if tracks:
        track_data = [dict(t) for t in tracks]
        tags.delall("TXXX:CADTracklist")
        tags["TXXX:CADTracklist"] = TXXX(
            encoding=3,
            desc="CADTracklist",
            text=json.dumps(track_data, ensure_ascii=False),
        )

    # Embedded artwork
    artwork_bytes = _load_artwork_bytes(row["artwork_path"])
    if artwork_bytes:
        mime = _mime_from_path(row["artwork_path"] or "")
        tags["APIC:"] = APIC(
            encoding=3,
            mime=mime,
            type=3,      # 3 = Cover (front)
            desc="Cover",
            data=artwork_bytes,
        )

    tags.save(str(mp3_file), v2_version=4)
    log.info("Tagged: %s", mp3_file.name)
    db.set_tag_done(episode_id)
    return True


def run_tag_batch(batch_size: int = 50) -> int:
    """Tag up to batch_size untagged episodes. Returns success count."""
    pending = db.get_pending_tag(limit=batch_size)
    if not pending:
        log.info("No episodes pending tagging.")
        return 0

    success = 0
    for row in pending:
        if tag_episode(row["id"]):
            success += 1

    return success
