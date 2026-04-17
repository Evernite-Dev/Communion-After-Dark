#!/usr/bin/env python3
"""
Communion After Dark Player — entry point.

Usage:
    python -m cad_player                         # auto-detect archive next to this install
    python -m cad_player --archive /path/to/archive
    python -m cad_player --db /path/to/cad_archive.db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio

from .library import Library
from .player_backend import AudioPlayer
from .window import MainWindow

APP_ID = "com.communionafterdark.CadPlayer"


def _find_archive_root() -> Path | None:
    """
    Walk upward from the module location looking for the 'archive' directory
    that the scraper creates.
    """
    here = Path(__file__).resolve()
    # Try up to 5 levels up
    candidate = here
    for _ in range(6):
        candidate = candidate.parent
        if (candidate / "archive").is_dir():
            return candidate / "archive"
    return None


class CadApplication(Adw.Application):
    def __init__(self, archive_root: Path, db_path: Path | None) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._archive_root = archive_root
        self._db_path = db_path
        self._library: Library | None = None
        self._player: AudioPlayer | None = None
        self.connect("activate", self._on_activate)

    def _on_activate(self, app: Adw.Application) -> None:
        # Force dark mode — the player theme is built around a black background.
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        self._player  = AudioPlayer()
        self._library = Library(
            archive_root=self._archive_root,
            db_path=self._db_path,
        )
        self._library.load()

        win = MainWindow(app, self._library, self._player)
        win.present()


def main() -> int:
    parser = argparse.ArgumentParser(description="Communion After Dark Player")
    parser.add_argument(
        "--archive",
        metavar="DIR",
        help="Path to the archive/ directory containing episode folders",
    )
    parser.add_argument(
        "--db",
        metavar="FILE",
        help="Path to cad_archive.db (overrides auto-detection)",
    )
    args, remaining = parser.parse_known_args()

    # Determine archive root
    if args.archive:
        archive_root = Path(args.archive).resolve()
    else:
        archive_root = _find_archive_root()
        if not archive_root:
            print(
                "Could not auto-detect the archive directory.\n"
                "Run the scraper first, or pass --archive /path/to/archive",
                file=sys.stderr,
            )
            return 1

    db_path: Path | None = None
    if args.db:
        db_path = Path(args.db).resolve()
    else:
        candidate = archive_root.parent / "data" / "cad_archive.db"
        if candidate.exists():
            db_path = candidate

    app = CadApplication(archive_root=archive_root, db_path=db_path)
    return app.run([sys.argv[0]] + remaining)


if __name__ == "__main__":
    sys.exit(main())
