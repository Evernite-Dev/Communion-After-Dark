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
from config import BASE_URL, RSS_URL, YEAR_ARCHIVE_URLS, SPECIAL_ARCHIVE_URLS
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
    """
    soup = BeautifulSoup(html, "lxml")
    urls: set[str] = set()
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        # Some hrefs are relative, some absolute; normalise all.
        if _LISTENNOW_RE.search(href):
            full = urljoin(base_url, href.split("?")[0])  # strip query params
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
