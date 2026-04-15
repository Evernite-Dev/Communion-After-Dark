"""
Phase 2 — Episode page scraper

For each episode URL already in the DB, fetches the Squarespace page and
extracts:
  - title, publication date
  - episode artwork URL
  - Buzzsprout direct-download audio URL
  - full tracklist (position, timestamp, artist, title, album, label, country)

The HTML structure of the CAD Squarespace site (as observed):
  - Artwork:  <img> inside a featured-image block or Open Graph <meta>
  - Audio:    a Buzzsprout direct link ending in .mp3 or ?download=true
  - Tracklist: plain text / formatted text in the page body with lines like:
        00:25 - Artist - Song - Album - Label - Country
    Some older episodes may use different separators or different fields.
"""

import json
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

import database as db
from config import BASE_URL, BATCH_SIZE, DELAY_BETWEEN_BATCHES
from http_client import get

import time

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Buzzsprout audio URL extraction
# ---------------------------------------------------------------------------

_BUZZSPROUT_RE = re.compile(
    r"https://www\.buzzsprout\.com/\d+/episodes/(\d+)-[^\"'\s>]+\.mp3",
    re.IGNORECASE,
)

def _extract_audio_url(soup: BeautifulSoup, page_text: str) -> tuple[str | None, int | None]:
    """
    Returns (direct_mp3_url, buzzsprout_episode_id) or (None, None).

    Search order:
      1. <a href="...buzzsprout...mp3..."> tags (download links)
      2. Raw text search for Buzzsprout MP3 URLs
      3. <audio src="..."> elements
    """
    # 1. Anchor tags
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        m = _BUZZSPROUT_RE.search(href)
        if m:
            url = href.split("?")[0]  # strip ?download=true etc.
            return url, int(m.group(1))

    # 2. Raw text search
    m = _BUZZSPROUT_RE.search(page_text)
    if m:
        url = m.group(0).split("?")[0]
        return url, int(m.group(1))

    # 3. <audio> element
    audio = soup.find("audio")
    if audio:
        src = audio.get("src") or (audio.find("source") or {}).get("src")
        if src:
            return src, None

    return None, None


# ---------------------------------------------------------------------------
# Artwork URL extraction
# ---------------------------------------------------------------------------

def _extract_artwork_url(soup: BeautifulSoup) -> str | None:
    # Open Graph image is the most reliable
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]

    # Squarespace CDN images in the post body
    for img in soup.find_all("img", src=True):
        src: str = img["src"]
        if "squarespace-cdn.com" in src or "static1.squarespace.com" in src:
            # Prefer the largest variant — strip Squarespace resize params
            return src.split("?")[0]

    return None


# ---------------------------------------------------------------------------
# Publication date extraction
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%B %d, %Y",       # January 6, 2025
    "%B %dth, %Y",     # April 13th, 2026
    "%b %d, %Y",       # Jan 6, 2025
    "%Y-%m-%d",        # 2025-01-06
]

def _parse_date(text: str) -> str | None:
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_pub_date(soup: BeautifulSoup) -> str | None:
    # 1. <time> tag with datetime attribute
    t = soup.find("time", attrs={"datetime": True})
    if t:
        dt_str = t["datetime"][:10]  # ISO date portion
        try:
            datetime.strptime(dt_str, "%Y-%m-%d")
            return dt_str
        except ValueError:
            pass

    # 2. Open Graph article:published_time
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        return meta["content"][:10]

    # 3. Schema.org datePublished
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            dp = data.get("datePublished", "")
            if dp:
                return dp[:10]
        except (json.JSONDecodeError, AttributeError):
            pass

    return None


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

_TITLE_SUFFIX_RE = re.compile(r"\s*[—\-–]\s*Communion After Dark\s*$", re.IGNORECASE)


def _extract_title(soup: BeautifulSoup) -> str | None:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return _TITLE_SUFFIX_RE.sub("", og["content"].strip())

    h1 = soup.find("h1")
    if h1:
        return _TITLE_SUFFIX_RE.sub("", h1.get_text(strip=True))

    title_tag = soup.find("title")
    if title_tag:
        return _TITLE_SUFFIX_RE.sub("", title_tag.get_text(strip=True))

    return None


# ---------------------------------------------------------------------------
# Description extraction
# ---------------------------------------------------------------------------

def _extract_description(soup: BeautifulSoup) -> str | None:
    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        return og["content"].strip()

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"].strip()

    return None


# ---------------------------------------------------------------------------
# Tracklist parsing
# ---------------------------------------------------------------------------

# Actual format observed in the wild:
#   1:13:48 Vol. A.D. (Ukraine) - Spirituvore - Album - Label
#   1:19:18 Die Sexual (Los Angeles CA) - Acid Never Dies - EP - Pylon Records
#
# Key differences from naive assumption:
#   • Timestamp is followed by a SPACE, not a dash
#   • Country / city is in parentheses at the end of the artist name
#   • \xa0 (non-breaking space) appears throughout
#   • Station-ID lines ("COMMUNION AFTER DARK") have a timestamp but no " - "
#     separator — these must be skipped

_TRACK_LINE_RE = re.compile(
    r"^\s*(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<rest>\S.+)$",
    re.UNICODE,
)

# Field separator is " - " (space – dash – space)
_FIELD_SEP_RE = re.compile(r"\s+-\s+")

# Country / city at the end of an artist string: "Blood Handsome (US)"
_COUNTRY_RE = re.compile(r"\s*\(([^)]+)\)\s*$")


def _parse_track_line(line: str, position: int) -> dict | None:
    # Normalise non-breaking spaces before anything else
    line = line.replace("\xa0", " ").strip()

    m = _TRACK_LINE_RE.match(line)
    if not m:
        return None

    timestamp = m.group("ts")
    rest = m.group("rest").replace("\xa0", " ").strip()

    parts = [p.strip() for p in _FIELD_SEP_RE.split(rest) if p.strip()]

    # Need at least artist AND song title; bare station-ID lines have no " - "
    if len(parts) < 2:
        return None

    track: dict = {"position": position, "timestamp": timestamp}

    artist_raw = parts[0]

    # Extract country from trailing parens: "Vol. A.D. (Ukraine)" → country=Ukraine
    country_m = _COUNTRY_RE.search(artist_raw)
    if country_m:
        track["country"] = country_m.group(1).strip()
        artist_raw = _COUNTRY_RE.sub("", artist_raw).strip()

    track["artist"] = artist_raw
    track["title"]  = parts[1] if len(parts) > 1 else ""
    track["album"]  = parts[2] if len(parts) > 2 else ""
    track["label"]  = parts[3] if len(parts) > 3 else ""

    return track


def _extract_tracklist(soup: BeautifulSoup) -> list[dict]:
    """
    Best-effort extraction of the tracklist from the episode body.
    Returns a list of track dicts (may be empty for older episodes).
    """
    tracks: list[dict] = []
    position = 1

    # Collect all text blocks from the main content area.
    # Squarespace body content is typically inside .sqs-block-content or
    # article/main tags.
    content_root = (
        soup.find("article")
        or soup.find("main")
        or soup.find(class_=re.compile(r"entry-content|post-content|sqs-block"))
        or soup.body
    )

    if not content_root:
        return tracks

    # Walk every paragraph, list item, and div — extract text line by line.
    for element in content_root.find_all(["p", "li", "div", "span"], recursive=True):
        text = element.get_text(separator="\n")
        for line in text.splitlines():
            t = _parse_track_line(line, position)
            if t:
                tracks.append(t)
                position += 1

    # Deduplicate (same timestamp may appear in nested elements)
    seen: set[str] = set()
    deduped: list[dict] = []
    for t in tracks:
        key = (t.get("timestamp"), t.get("artist"), t.get("title"))
        if key not in seen:
            seen.add(key)
            deduped.append(t)

    # Re-number positions after dedup
    for i, t in enumerate(deduped, start=1):
        t["position"] = i

    return deduped


# ---------------------------------------------------------------------------
# Main per-episode scrape
# ---------------------------------------------------------------------------

def scrape_episode(episode_id: int, page_url: str) -> bool:
    """
    Fetch and parse one episode page.  Saves results to DB.
    Returns True on success, False on failure.
    """
    log.info("Scraping episode #%d: %s", episode_id, page_url)
    try:
        resp = get(page_url)
    except Exception as exc:
        msg = f"HTTP error: {exc}"
        log.error("  %s", msg)
        db.set_scrape_error(episode_id, msg)
        return False

    soup = BeautifulSoup(resp.text, "lxml")

    title = _extract_title(soup)
    pub_date = _extract_pub_date(soup)
    description = _extract_description(soup)
    artwork_url = _extract_artwork_url(soup)
    audio_url, buzzsprout_id = _extract_audio_url(soup, resp.text)
    tracks = _extract_tracklist(soup)

    log.info(
        "  title=%r  date=%s  tracks=%d  audio=%s",
        title, pub_date, len(tracks), "yes" if audio_url else "NO",
    )

    metadata = {
        "title": title,
        "pub_date": pub_date,
        "description": description,
        "artwork_url": artwork_url,
        "audio_url": audio_url,
        "buzzsprout_id": buzzsprout_id,
    }
    # Remove None values so we don't overwrite existing data with NULL
    metadata = {k: v for k, v in metadata.items() if v is not None}

    db.set_scrape_done(episode_id, **metadata)

    if not audio_url:
        db.set_audio_unavailable(episode_id)

    if tracks:
        db.insert_tracks(episode_id, tracks)

    return True


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_scrape_batch(batch_size: int = BATCH_SIZE) -> int:
    """
    Scrape up to batch_size pending episodes.
    Returns number of successfully scraped episodes.
    """
    pending = db.get_pending_scrape(limit=batch_size)
    if not pending:
        log.info("No pending episodes to scrape.")
        return 0

    success = 0
    for i, row in enumerate(pending, start=1):
        ok = scrape_episode(row["id"], row["page_url"])
        if ok:
            success += 1
        if i % BATCH_SIZE == 0 and i < len(pending):
            log.info("Batch pause (%.0fs)…", DELAY_BETWEEN_BATCHES)
            time.sleep(DELAY_BETWEEN_BATCHES)

    return success
