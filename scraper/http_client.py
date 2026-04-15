"""
Shared HTTP client with rate-limiting and retry logic.

Every outbound request in the archiver goes through get() or download_file()
so the rate limits are enforced in one place.
"""

import time
import logging
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    USER_AGENT,
    DELAY_BETWEEN_REQUESTS,
    MAX_RETRIES,
    RETRY_AFTER_429,
    REQUEST_TIMEOUT,
)

log = logging.getLogger(__name__)

_last_request_time: float = 0.0


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session_instance: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session_instance
    if _session_instance is None:
        _session_instance = _session()
    return _session_instance


def _throttle() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < DELAY_BETWEEN_REQUESTS:
        sleep_for = DELAY_BETWEEN_REQUESTS - elapsed
        log.debug("Rate-limiting: sleeping %.1fs", sleep_for)
        time.sleep(sleep_for)
    _last_request_time = time.monotonic()


def get(url: str, **kwargs) -> requests.Response:
    """Throttled GET; raises on non-2xx after retries."""
    _throttle()
    session = _get_session()
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            log.warning("Request error (%s), retry %d/%d", exc, attempt + 1, MAX_RETRIES)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", RETRY_AFTER_429))
            log.warning("429 Too Many Requests — waiting %.0fs before retry", wait)
            time.sleep(wait)
            continue

        resp.raise_for_status()
        return resp

    raise RuntimeError(f"Failed to GET {url} after {MAX_RETRIES} retries")


def download_file(url: str, dest: Path, *, chunk_size: int = 65536) -> None:
    """
    Stream a file to disk.  Creates parent directories automatically.
    Writes to a .tmp file first then renames on success (atomic-ish).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    _throttle()
    session = _get_session()

    log.info("Downloading %s → %s", url, dest.name)
    with session.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    fh.write(chunk)

    tmp.rename(dest)
    log.info("Saved %s (%.1f MB)", dest.name, dest.stat().st_size / 1_048_576)
