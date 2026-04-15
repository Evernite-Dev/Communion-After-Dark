#!/usr/bin/env python3
"""
Communion After Dark — Personal Archive Tool
============================================

Usage examples
--------------

# First run: discover all episode URLs across every year
python main.py discover --all-years

# Discover only recent episodes via RSS (fastest, recommended first step)
python main.py discover --rss

# Scrape metadata + tracklists for up to 20 episodes
python main.py scrape --batch 20

# Download audio for up to 5 episodes (conservative first test)
python main.py download --audio --batch 5

# Download all pending artwork
python main.py download --artwork --batch 50

# Embed ID3 tags into downloaded MP3s
python main.py tag

# Show current archive statistics
python main.py status

# Full pipeline in one command (discover → scrape → download → tag)
# Run repeatedly over days/weeks until complete.
python main.py run --batch 10

# Re-write all metadata.json files (e.g. after tracklist fixes)
python main.py refresh-metadata
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure the scraper package directory is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

import database as db
import crawler
import extractor
import downloader
import tagger
from config import BATCH_SIZE, DELAY_BETWEEN_BATCHES

console = Console()


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


# ---------------------------------------------------------------------------
# Status display
# ---------------------------------------------------------------------------

def cmd_status(_args) -> None:
    s = db.stats()
    table = Table(title="CAD Archive Status", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    rows = [
        ("Total episodes discovered", s["total"]),
        ("Metadata scraped",          s["scraped"]),
        ("Audio downloaded",          s["audio_done"]),
        ("No audio available",        s["no_audio"]),
        ("Artwork downloaded",        s["artwork_done"]),
        ("ID3 tags written",          s["tagged"]),
        ("Scrape errors",             s["scrape_errors"]),
        ("Audio errors",              s["audio_errors"]),
    ]
    for label, value in rows:
        table.add_row(label, str(value or 0))

    console.print(table)

    remaining_audio = (s["total"] or 0) - (s["audio_done"] or 0) - (s["no_audio"] or 0)
    if remaining_audio > 0:
        console.print(
            f"\n[yellow]~{remaining_audio} episodes still need audio downloaded.[/yellow]"
        )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_discover(args) -> None:
    db.init_db()
    if args.rss or args.all:
        console.print("[bold]Crawling RSS feed…[/bold]")
        n = crawler.crawl_rss()
        console.print(f"  RSS: {n} episodes processed")

    if args.all_years or args.all:
        years = None  # all years
        console.print("[bold]Crawling year-archive pages…[/bold]")
        n = crawler.crawl_year_pages(years=years)
        console.print(f"  Year pages: {n} episode URLs discovered")
    elif args.year:
        console.print(f"[bold]Crawling {args.year} archive page…[/bold]")
        n = crawler.crawl_year_pages(years=[args.year])
        console.print(f"  {args.year}: {n} episode URLs discovered")

    cmd_status(args)


def cmd_scrape(args) -> None:
    db.init_db()
    batch = args.batch or BATCH_SIZE
    console.print(f"[bold]Scraping up to {batch} episode pages…[/bold]")
    n = extractor.run_scrape_batch(batch_size=batch)
    console.print(f"  Scraped: {n} episodes")
    cmd_status(args)


def cmd_download(args) -> None:
    db.init_db()
    batch = args.batch or BATCH_SIZE

    if args.audio or (not args.artwork):
        console.print(f"[bold]Downloading audio for up to {batch} episodes…[/bold]")
        n = downloader.download_audio_batch(batch_size=batch)
        console.print(f"  Audio downloaded: {n}")

    if args.artwork or (not args.audio):
        console.print(f"[bold]Downloading artwork for up to {batch * 3} episodes…[/bold]")
        n = downloader.download_artwork_batch(batch_size=batch * 3)
        console.print(f"  Artwork downloaded: {n}")

    cmd_status(args)


def cmd_tag(args) -> None:
    db.init_db()
    batch = args.batch or 50
    console.print(f"[bold]Tagging up to {batch} MP3 files…[/bold]")
    n = tagger.run_tag_batch(batch_size=batch)
    console.print(f"  Tagged: {n} files")


def cmd_refresh_metadata(_args) -> None:
    db.init_db()
    console.print("[bold]Re-writing metadata.json files…[/bold]")
    n = downloader.write_all_metadata_json()
    console.print(f"  Written: {n} files")


def cmd_run(args) -> None:
    """
    Full pipeline: discover (RSS) → scrape → download → tag.
    Designed to be run repeatedly on a schedule until the archive is complete.
    """
    db.init_db()
    batch = args.batch or BATCH_SIZE

    console.rule("[bold green]Communion After Dark Archiver[/bold green]")

    # Step 1: RSS discovery (always fast, pull latest)
    console.print("\n[bold]Step 1/4 — RSS discovery[/bold]")
    crawler.crawl_rss()

    # Step 2: Scrape pending episode pages
    console.print(f"\n[bold]Step 2/4 — Scraping metadata (batch={batch})[/bold]")
    scraped = extractor.run_scrape_batch(batch_size=batch)
    console.print(f"  Scraped: {scraped}")

    if scraped:
        console.print(f"  Pausing {DELAY_BETWEEN_BATCHES}s between phases…")
        time.sleep(DELAY_BETWEEN_BATCHES)

    # Step 3: Download audio
    console.print(f"\n[bold]Step 3/4 — Downloading audio (batch={batch})[/bold]")
    audio_n = downloader.download_audio_batch(batch_size=batch)
    console.print(f"  Audio: {audio_n}")

    # Step 4: Artwork + tagging
    console.print(f"\n[bold]Step 4/4 — Artwork + tagging[/bold]")
    downloader.download_artwork_batch(batch_size=batch * 3)
    tagged = tagger.run_tag_batch(batch_size=batch * 5)
    console.print(f"  Tagged: {tagged}")

    console.rule()
    cmd_status(args)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Communion After Dark personal archive tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    sub = p.add_subparsers(dest="command", required=True)

    # discover
    d = sub.add_parser("discover", help="Crawl for episode URLs")
    d.add_argument("--rss",       action="store_true", help="Parse RSS feed")
    d.add_argument("--all-years", action="store_true", help="Crawl all year-archive pages")
    d.add_argument("--all",       action="store_true", help="RSS + all year pages")
    d.add_argument("--year",      type=int,            help="Crawl a single year (e.g. 2019)")
    d.set_defaults(func=cmd_discover)

    # scrape
    s = sub.add_parser("scrape", help="Scrape episode pages for metadata + tracklists")
    s.add_argument("--batch", type=int, help=f"Episodes per batch (default {BATCH_SIZE})")
    s.set_defaults(func=cmd_scrape)

    # download
    dl = sub.add_parser("download", help="Download audio and/or artwork")
    dl.add_argument("--audio",   action="store_true", help="Download audio only")
    dl.add_argument("--artwork", action="store_true", help="Download artwork only")
    dl.add_argument("--batch",   type=int,            help=f"Episodes per batch (default {BATCH_SIZE})")
    dl.set_defaults(func=cmd_download)

    # tag
    t = sub.add_parser("tag", help="Embed ID3 tags into downloaded MP3 files")
    t.add_argument("--batch", type=int, help="Files per batch (default 50)")
    t.set_defaults(func=cmd_tag)

    # status
    st = sub.add_parser("status", help="Show archive statistics")
    st.set_defaults(func=cmd_status)

    # refresh-metadata
    rm = sub.add_parser("refresh-metadata", help="Re-write all metadata.json files")
    rm.set_defaults(func=cmd_refresh_metadata)

    # run (full pipeline)
    r = sub.add_parser("run", help="Full pipeline: discover → scrape → download → tag")
    r.add_argument("--batch", type=int, help=f"Episodes per batch (default {BATCH_SIZE})")
    r.set_defaults(func=cmd_run)

    return p


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)
    db.init_db()
    args.func(args)


if __name__ == "__main__":
    main()
