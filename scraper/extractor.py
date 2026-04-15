"""
Phase 2 — Episode page scraper

For each episode URL already in the DB, fetches the Squarespace page and
extracts:
  - title, publication date
  - episode artwork URL
  - Audio URL (Buzzsprout direct MP3, self-hosted direct MP3, or Mixcloud page)
  - full tracklist (position, timestamp, artist, title, album, label, country)

Audio source detection order:
  1. Buzzsprout MP3 link (2021-present)
  2. Direct MP3 href in page body via ?format=json-pretty API (2011-2015)
     Hosted on: cad.tieranny.com, communionafterdark.com, static1.squarespace.com
  3. Mixcloud embed iframe (2016-2023)
  4. <audio> tag fallback

The Squarespace ?format=json-pretty endpoint returns the full post body HTML
including media embeds that are JavaScript-rendered in the browser and therefore
invisible to a plain page scrape.
"""

import json
import logging
import re
import time
from datetime import datetime
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

import database as db
from config import BASE_URL, BATCH_SIZE, DELAY_BETWEEN_BATCHES
from http_client import get

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audio URL extraction — multiple hosting providers
# ---------------------------------------------------------------------------

_BUZZSPROUT_RE = re.compile(
    r"https://www\.buzzsprout\.com/\d+/episodes/(\d+)-[^\"'\s>]+\.mp3",
    re.IGNORECASE,
)

# Any direct MP3 link (self-hosted on tieranny.com, communionafterdark.com,
# static1.squarespace.com, etc.)
_DIRECT_MP3_RE = re.compile(
    r'https?://[^\s"\'<>]+\.mp3(?:[^\s"\'<>]*)?',
    re.IGNORECASE,
)

# Mixcloud widget iframe: feed= param holds the URL-encoded Mixcloud track URL
_MIXCLOUD_WIDGET_RE = re.compile(
    r'mixcloud\.com/widget/iframe/[^"\'<>\s]*feed=([^&"\'<>\s]+)',
    re.IGNORECASE,
)


def _extract_mixcloud_url(text: str) -> str | None:
    """Extract a clean Mixcloud track URL from a widget iframe embed."""
    m = _MIXCLOUD_WIDGET_RE.search(text)
    if m:
        decoded = unquote(m.group(1))
        # Ensure it's a proper Mixcloud track URL
        if "mixcloud.com" in decoded:
            return decoded.rstrip("/") + "/"
    return None


def _fetch_json_body(page_url: str) -> str:
    """
    Fetch the Squarespace ?format=json-pretty endpoint.
    Returns the post body HTML string (may be empty on failure).

    This endpoint exposes the full rendered body including audio embeds that
    are JavaScript-rendered and invisible in the static page HTML.
    """
    try:
        resp = get(page_url + "?format=json-pretty")
        data = resp.json()
        return data.get("item", {}).get("body", "") or ""
    except Exception as exc:
        log.debug("JSON body fetch failed for %s: %s", page_url, exc)
        return ""


def _extract_audio_url(
    soup: BeautifulSoup, page_text: str, body_html: str = ""
) -> tuple[str | None, int | None, str | None]:
    """
    Returns (audio_url, buzzsprout_episode_id, source) or (None, None, None).

    source is one of: 'buzzsprout' | 'direct' | 'mixcloud'

    Search order:
      1. Buzzsprout MP3 — anchor tags, then raw text
      2. Direct MP3 in JSON body HTML (self-hosted: tieranny, sqsp CDN, cad.com)
      3. Mixcloud widget embed (in body HTML or page text)
      4. <audio src="..."> element
    """
    combined = body_html + "\n" + page_text

    # 1. Buzzsprout anchor tags
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        m = _BUZZSPROUT_RE.search(href)
        if m:
            url = href.split("?")[0]
            return url, int(m.group(1)), "buzzsprout"

    # 2. Buzzsprout anywhere in combined text
    m = _BUZZSPROUT_RE.search(combined)
    if m:
        url = m.group(0).split("?")[0]
        return url, int(m.group(1)), "buzzsprout"

    # 3. Direct MP3 in JSON body (self-hosted archives)
    if body_html:
        m = _DIRECT_MP3_RE.search(body_html)
        if m:
            url = m.group(0).split("?")[0]
            return url, None, "direct"

    # 4. Mixcloud embed
    mixcloud_url = _extract_mixcloud_url(combined)
    if mixcloud_url:
        return mixcloud_url, None, "mixcloud"

    # 5. <audio> element fallback
    audio = soup.find("audio")
    if audio:
        src = audio.get("src") or (audio.find("source") or {}).get("src")
        if src:
            return src, None, "direct"

    return None, None, None


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

    # Fetch the Squarespace JSON body — exposes audio links hidden behind JS
    body_html = _fetch_json_body(page_url)

    # Use JSON body for tracklist too — it's the rendered content
    body_soup = BeautifulSoup(body_html, "lxml") if body_html else soup

    title = _extract_title(soup)
    pub_date = _extract_pub_date(soup)
    description = _extract_description(soup)
    artwork_url = _extract_artwork_url(soup)
    audio_url, buzzsprout_id, audio_source = _extract_audio_url(soup, resp.text, body_html)
    tracks = _extract_tracklist(body_soup)

    log.info(
        "  title=%r  date=%s  tracks=%d  audio=%s (%s)",
        title, pub_date, len(tracks),
        "yes" if audio_url else "NO",
        audio_source or "-",
    )

    metadata = {
        "title": title,
        "pub_date": pub_date,
        "description": description,
        "artwork_url": artwork_url,
        "audio_url": audio_url,
        "audio_source": audio_source,
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


# ---------------------------------------------------------------------------
# Audio URL refresh (targeted — for no_audio episodes)
# ---------------------------------------------------------------------------

def refresh_audio_url(episode_id: int, page_url: str) -> bool:
    """
    Lightweight refresh: re-fetch the audio URL for a single episode without
    re-scraping the full tracklist.  Used to recover episodes that were scraped
    before multi-source audio detection was added.

    Returns True if an audio URL was found and saved.
    """
    log.debug("Refreshing audio URL for ep#%d: %s", episode_id, page_url)
    try:
        body_html = _fetch_json_body(page_url)
        resp = get(page_url)
        soup = BeautifulSoup(resp.text, "lxml")
        audio_url, buzzsprout_id, audio_source = _extract_audio_url(
            soup, resp.text, body_html
        )
    except Exception as exc:
        log.error("Audio refresh error for ep#%d: %s", episode_id, exc)
        return False

    if audio_url:
        update: dict = {
            "audio_url": audio_url,
            "audio_source": audio_source,
            "audio_status": "pending",
        }
        if buzzsprout_id:
            update["buzzsprout_id"] = buzzsprout_id
        db.update_episode_metadata(episode_id, **update)
        log.info("  ep#%d — %s  %s", episode_id, audio_source, audio_url[:70])
        return True

    log.debug("  ep#%d — still no audio", episode_id)
    return False


def run_audio_refresh_batch(batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    """
    Refresh audio URLs for up to batch_size no_audio episodes.
    Returns (found_count, checked_count).
    """
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, page_url FROM episodes
            WHERE audio_status = 'no_audio'
            ORDER BY year DESC, id ASC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()

    if not rows:
        log.info("No no_audio episodes to refresh.")
        return 0, 0

    found = 0
    for i, row in enumerate(rows, start=1):
        if refresh_audio_url(row["id"], row["page_url"]):
            found += 1
        if i % BATCH_SIZE == 0 and i < len(rows):
            log.info("Batch pause (%.0fs)…", DELAY_BETWEEN_BATCHES)
            time.sleep(DELAY_BETWEEN_BATCHES)

    return found, len(rows)
