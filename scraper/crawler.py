"""
Phase 1 — Discovery

Crawls the RSS feed and every year-archive page to populate the episodes
table with Squarespace episode URLs.  No audio is downloaded here.

Run order:
    1. crawl_rss()          ← fast, uses official feed, covers ~100 recent eps
    2. crawl_year_pages()   ← scrapes listing pages to find older episodes
"""

import logging
import re
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

import database as db
from config import BASE_URL, RSS_URL, MIXCLOUD_PROFILE, YEAR_ARCHIVE_URLS, SPECIAL_ARCHIVE_URLS
from http_client import get

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RSS feed
# ---------------------------------------------------------------------------

def crawl_rss() -> int:
    """
    Parse the official Buzzsprout RSS feed.
    Inserts episodes that aren't already in the DB.
    Returns number of new episodes inserted.
    """
    log.info("Fetching RSS feed: %s", RSS_URL)
    feed = feedparser.parse(RSS_URL)

    if feed.bozo:
        log.warning("RSS feed parse warning: %s", feed.bozo_exception)

    new_count = 0
    for entry in feed.entries:
        # Derive the Squarespace page URL from the episode link if present,
        # otherwise use the Buzzsprout episode page as a fallback.
        # The RSS <link> typically points to the Squarespace episode page.
        page_url = entry.get("link", "")
        if not page_url:
            log.warning("RSS entry without link: %s", entry.get("title"))
            continue

        # Normalise to full URL
        if not page_url.startswith("http"):
            page_url = urljoin(BASE_URL, page_url)

        # Skip anything that isn't an individual episode page
        if "/listennow/" not in page_url:
            log.debug("RSS: skipping non-episode URL: %s", page_url)
            continue

        # Try to determine the year from pubDate
        year = None
        published = entry.get("published_parsed")
        if published:
            year = published.tm_year

        episode_id = db.upsert_episode(page_url, year=year, category="annual")
        log.debug("RSS: %s  →  ep#%d", entry.get("title", "?"), episode_id)
        new_count += 1

    log.info("RSS crawl complete — %d episodes in feed", new_count)
    return new_count


# ---------------------------------------------------------------------------
# Year-archive pages
# ---------------------------------------------------------------------------

_LISTENNOW_RE = re.compile(r"/listennow/[a-z0-9]+", re.IGNORECASE)


def _extract_episode_links(html: str, base_url: str) -> list[str]:
    """
    Return a deduplicated list of full episode page URLs found in html.
    Looks for /listennow/<slug> href patterns.

    Excluded URL patterns (not individual episodes):
      /listennow/tag/...       — Squarespace tag listing pages
      /listennow/category/...  — Squarespace category listing pages
    """
    soup = BeautifulSoup(html, "lxml")
    urls: set[str] = set()
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if not _LISTENNOW_RE.search(href):
            continue
        # Strip both query params and fragments — fragments are client-side
        # anchors and must not be stored as distinct episode URLs.
        clean = href.split("?")[0].split("#")[0]
        # Skip tag/category listing pages — they are not individual episodes.
        clean_lower = clean.lower()
        if "/listennow/tag/" in clean_lower or "/listennow/category/" in clean_lower:
            continue
        full = urljoin(base_url, clean)
        urls.add(full)
    return sorted(urls)


def _crawl_listing_page(path: str, year: int | None, category: str) -> int:
    url = urljoin(BASE_URL, path)
    log.info("Crawling listing page: %s", url)

    try:
        resp = get(url)
    except Exception as exc:
        log.error("Failed to fetch listing page %s: %s", url, exc)
        return 0

    links = _extract_episode_links(resp.text, BASE_URL)
    new_count = 0
    for link in links:
        db.upsert_episode(link, year=year, category=category)
        new_count += 1
        log.debug("  Discovered: %s", link)

    log.info("  → %d episode links found", new_count)
    return new_count


def crawl_year_pages(years: list[int] | None = None) -> int:
    """
    Crawl all year-archive listing pages (or a subset if years is given).
    Returns total number of episode URLs discovered.
    """
    total = 0
    targets = {y: p for y, p in YEAR_ARCHIVE_URLS.items()
               if years is None or y in years}

    for year, path in sorted(targets.items(), reverse=True):
        total += _crawl_listing_page(path, year=year, category="annual")

    for name, path in SPECIAL_ARCHIVE_URLS.items():
        cat = name.split("-")[0] if "-" in name else name
        total += _crawl_listing_page(path, year=None, category=cat)

    log.info("Year-page crawl complete — %d episode URLs discovered total", total)
    return total


# ---------------------------------------------------------------------------
# Mixcloud API — direct audio URL discovery
# ---------------------------------------------------------------------------

def crawl_mixcloud(limit: int = 5) -> int:
    """
    Query the Mixcloud API for recent uploads by MIXCLOUD_PROFILE.
    For any upload whose date matches an episode currently marked no_audio,
    set the Mixcloud URL directly so the downloader can pick it up via yt-dlp.

    This is faster than waiting for the Squarespace page to embed the widget,
    since Mixcloud receives the upload before the site embed is updated.

    Returns number of episodes updated.
    """
    api_url = f"https://api.mixcloud.com/{MIXCLOUD_PROFILE}/cloudcasts/?limit={limit}"
    log.info("Querying Mixcloud API: %s", api_url)
    try:
        resp = get(api_url)
        data = resp.json()
    except Exception as exc:
        log.warning("Mixcloud API fetch failed: %s", exc)
        return 0

    cloudcasts = data.get("data", [])
    if not cloudcasts:
        log.info("Mixcloud API returned no recent uploads.")
        return 0

    updated = 0
    for cast in cloudcasts:
        url = cast.get("url", "").rstrip("/") + "/"
        created = (cast.get("created_time") or "")[:10]  # YYYY-MM-DD
        if not url or not created:
            continue
        n = db.apply_mixcloud_url(created, url)
        if n:
            log.info("  Mixcloud match on %s — updated %d episode(s): %s", created, n, url[:70])
            updated += n

    log.info("Mixcloud crawl complete — %d episode(s) updated", updated)
    return updated
