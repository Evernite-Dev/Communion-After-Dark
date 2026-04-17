"""
Main application window — GTK4 + libadwaita

Layout (3-panel):
┌─────────────────────────────────────────────────────────┐
│  HeaderBar: [≡ sidebar]  Title  [search]  [vol]         │
├──────────┬──────────────────────────┬────────────────────┤
│          │                          │                    │
│  Year    │  Episode list            │  Track list +      │
│  list    │  (title + date)          │  artwork +         │
│          │                          │  description       │
├──────────┴──────────────────────────┴────────────────────┤
│  [◀◀] [▶/⏸] [▶▶]  progress ─────────────  🔊 00:00/2:00:00 │
└─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os
from datetime import datetime as _dt
from pathlib import Path
from typing import TYPE_CHECKING

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gtk, GdkPixbuf, GLib, Gio, Pango

from .favorites import Favorite, FavoritesStore
from .library import Episode, Library, TrackResult
from .player_backend import AudioPlayer, PlayerState, format_time

if TYPE_CHECKING:
    pass

APP_ID = "com.communionafterdark.CadPlayer"

_BANNER_HEIGHT = 120


def _format_pub_date(date_str: str) -> str:
    """Format a YYYY-MM-DD date string as 'April 13, 2026'."""
    try:
        return _dt.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except (ValueError, TypeError):
        return date_str or ""


def _timestamp_to_seconds(ts: str) -> int:
    """
    Parse a tracklist timestamp string into an integer number of seconds.

    Handles both MM:SS and H:MM:SS formats, e.g.:
        "00:25"   →  25
        "23:11"   →  1391
        "1:04:02" →  3842
    """
    try:
        parts = [int(p) for p in ts.strip().split(":")]
    except ValueError:
        return 0
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def _apply_heart_style(btn: Gtk.ToggleButton, active: bool) -> None:
    """
    Give the heart button a filled (accent) look when active, dim when not.
    Uses libadwaita CSS classes — no custom CSS required.
    """
    if active:
        btn.add_css_class("accent")
        btn.remove_css_class("dim-label")
    else:
        btn.remove_css_class("accent")
        btn.add_css_class("dim-label")


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, library: Library, player: AudioPlayer) -> None:
        super().__init__(application=app, title="Communion After Dark")
        self.set_default_size(1200, 700)
        self.set_size_request(800, 500)

        self._library  = library
        self._player   = player
        self._current_episode: Episode | None = None
        self._episode_list: list[Episode] = []
        self._current_index: int = -1
        # List of (start_seconds, row) for the currently displayed tracklist.
        # Used to highlight the active track during playback.
        self._track_rows: list[tuple[int, Gtk.ListBoxRow]] = []
        self._active_track_row: Gtk.ListBoxRow | None = None
        # True when the sidebar "Favorites" entry is selected.
        self._favorites_mode: bool = False
        # True when the episode list is showing track-level search results.
        self._track_search_mode: bool = False
        # Episodes that have been played this session — used to dismiss the new-ep banner.
        self._listened_ids: set[int] = set()
        self._banner_stack: Gtk.Stack | None = None
        self._banner_newest_id: int | None = None

        self._favorites = FavoritesStore(
            db_path=library.db_path,
            archive_root=library.archive_root,
        )

        self._build_ui()
        self._connect_player()
        self._populate_years()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _load_css(self) -> None:
        # ── Font faces ────────────────────────────────────────────────────────
        # Build @font-face rules from bundled font files.  Silently skips any
        # file that hasn't been placed yet so the app still runs without fonts.
        fonts_dir = Path(__file__).parent / "fonts"
        font_faces = ""
        if fonts_dir.is_dir():
            for filename, weight, style in [
                ("MinervaModern-Bold.ttf",       400, "normal"),
                ("MinervaModern-Italic.ttf",      400, "italic"),
                ("MinervaModern-Black.ttf",       700, "normal"),
                ("MinervaModern-BoldItalic.ttf",  700, "italic"),
                ("MinervaModern-BlackItalic.ttf", 900, "normal"),
            ]:
                font_file = fonts_dir / filename
                if font_file.exists():
                    uri = font_file.as_uri()
                    font_faces += (
                        f"@font-face {{"
                        f" font-family: 'minerva-modern';"
                        f" src: url('{uri}');"
                        f" font-weight: {weight};"
                        f" font-style: {style};"
                        f" }}\n"
                    )

        css = (font_faces + """
        /* ── Libadwaita palette overrides ───────────────────────────────── */
        @define-color window_bg_color    #000000;
        @define-color window_fg_color    #ababab;
        @define-color view_bg_color      #0a0a0a;
        @define-color view_fg_color      #ababab;
        @define-color headerbar_bg_color #000000;
        @define-color headerbar_fg_color #ffffff;
        @define-color sidebar_bg_color   #060606;
        @define-color card_bg_color      #0d0d0d;
        @define-color card_fg_color      #ababab;
        @define-color popover_bg_color   #111111;
        @define-color accent_bg_color    #ff0505;
        @define-color accent_fg_color    #ffffff;
        @define-color accent_color       #ff0505;

        /* ── Global font ─────────────────────────────────────────────────── */
        label, button, entry, searchentry, headerbar * {
            font-family: 'minerva-modern', 'Helvetica Neue', Arial, sans-serif;
        }
        /* Keep numeric time labels monospaced */
        .numeric {
            font-family: monospace;
        }

        /* ── Typography hierarchy ────────────────────────────────────────── */
        .title-1, .title-2, .title-3, .title-4 {
            color: #ffffff;
        }
        .body {
            color: #ababab;
        }
        .caption {
            color: #666666;
        }
        .dim-label {
            color: #555555;
        }

        /* ── Header bar ──────────────────────────────────────────────────── */
        headerbar {
            background-color: #000000;
            border-bottom: 1px solid #1a1a1a;
            box-shadow: none;
        }
        headerbar windowtitle .title {
            color: #ffffff;
        }

        /* ── Navigation sidebar ──────────────────────────────────────────── */
        .navigation-sidebar {
            background-color: #060606;
        }
        .navigation-sidebar row {
            border-radius: 6px;
            color: #ababab;
        }
        .navigation-sidebar row:hover {
            background-color: #111111;
            color: #ffffff;
        }
        .navigation-sidebar row:selected,
        .navigation-sidebar row:selected:focus {
            background-color: #1a0000;
            color: #ff0505;
        }

        /* ── Episode / track lists ───────────────────────────────────────── */
        .boxed-list {
            background-color: #0a0a0a;
        }
        .boxed-list > row {
            background-color: #0a0a0a;
            border-bottom: 1px solid #141414;
        }
        .boxed-list > row:hover {
            background-color: #111111;
        }
        .boxed-list > row:selected,
        .boxed-list > row:selected:focus {
            background-color: #1a0000;
            color: #ffffff;
        }

        /* ── Seek / progress bar ─────────────────────────────────────────── */
        scale trough {
            background-color: #1a1a1a;
            border-radius: 4px;
            min-height: 4px;
        }
        scale trough highlight {
            background-color: #ff0505;
            border-radius: 4px;
        }
        scale slider {
            background-color: #ff0505;
            min-width: 14px;
            min-height: 14px;
            border-radius: 50%;
        }

        /* ── Buttons ─────────────────────────────────────────────────────── */
        button.suggested-action {
            background-color: #ff0505;
            color: #ffffff;
        }
        button.suggested-action:hover {
            background-color: #cc0404;
        }
        button.circular {
            color: #ababab;
        }
        button.circular:hover {
            color: #ffffff;
            background-color: #1a1a1a;
        }
        button.circular.accent {
            color: #ff0505;
        }

        /* ── Search entry ────────────────────────────────────────────────── */
        searchentry {
            background-color: #111111;
            color: #ababab;
            border: 1px solid #2a2a2a;
            border-radius: 6px;
        }
        searchentry:focus-within {
            border-color: #ff0505;
        }

        /* ── Scrollbars ──────────────────────────────────────────────────── */
        scrollbar {
            background-color: transparent;
        }
        scrollbar slider {
            background-color: #333333;
            border-radius: 10px;
            min-width: 6px;
            min-height: 6px;
        }
        scrollbar slider:hover {
            background-color: #ff0505;
        }

        /* ── Separators ──────────────────────────────────────────────────── */
        separator {
            background-color: #1a1a1a;
        }

        /* ── Artwork card ────────────────────────────────────────────────── */
        .card {
            background-color: #0d0d0d;
            border: 1px solid #1a1a1a;
            border-radius: 8px;
        }

        /* ── Playbar toolbar ─────────────────────────────────────────────── */
        .toolbar {
            background-color: #000000;
            border-top: 1px solid #1a1a1a;
        }

        /* ── Banner strip ────────────────────────────────────────────────── */
        .cad-banner-strip {
            background-color: #000000;
        }
        .cad-new-tag {
            color: #ff0505;
            font-size: 0.7em;
            font-weight: bold;
            letter-spacing: 0.15em;
            text-transform: uppercase;
        }
        .cad-banner-ep-title {
            color: #ffffff;
            font-size: 1.05em;
            font-weight: bold;
        }
        .cad-banner-ep-date {
            color: #ababab;
            font-size: 0.85em;
        }
        """).encode()

        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_banner(self) -> Gtk.Widget:
        """
        Persistent banner strip always shown above the 3-panel area.

        States (managed via Gtk.Stack):
          'logo'    — full-width site logo image (cad_banner.jpg/.jpeg)
          'episode' — square episode artwork left + title/date centred right;
                      shown when the newest episode hasn't been played yet.

        Switches back to 'logo' once the newest episode is played.
        """
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_hexpand(True)

        self._banner_stack = Gtk.Stack()
        self._banner_stack.set_hexpand(True)
        self._banner_stack.set_size_request(-1, _BANNER_HEIGHT)
        self._banner_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._banner_stack.set_transition_duration(300)

        # ── Logo page ────────────────────────────────────────────────────
        assets_dir = Path(__file__).parent / "assets"
        logo_path: Path | None = None
        for name in ("cad_banner.jpg", "cad_banner.jpeg"):
            candidate = assets_dir / name
            if candidate.exists():
                logo_path = candidate
                break

        if logo_path:
            logo_pic = Gtk.Picture.new_for_filename(str(logo_path))
            logo_pic.set_content_fit(Gtk.ContentFit.COVER)
            logo_pic.set_can_shrink(True)
        else:
            logo_pic = Gtk.Box()
            logo_pic.add_css_class("cad-banner-strip")

        self._banner_stack.add_named(logo_pic, "logo")

        # ── New episode page ─────────────────────────────────────────────
        if self._library.episodes:
            newest = self._library.episodes[0]
            if newest.audio_path:
                ep_page = self._build_episode_banner_page(newest)
                self._banner_stack.add_named(ep_page, "episode")
                self._banner_stack.set_visible_child_name("episode")
                self._banner_newest_id = newest.id

        outer.append(self._banner_stack)
        outer.append(Gtk.Separator())
        return outer

    def _build_episode_banner_page(self, episode: Episode) -> Gtk.Widget:
        """
        New-episode banner content: 1:1 square artwork on the left,
        episode title and formatted date centred in the remaining space.
        The entire widget acts as a button — clicking plays the episode.
        """
        btn = Gtk.Button()
        btn.set_has_frame(False)
        btn.set_hexpand(True)
        btn.set_vexpand(True)
        btn.add_css_class("cad-banner-strip")
        btn.connect("clicked", lambda _: self._on_banner_play(episode))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row.set_hexpand(True)
        row.set_vexpand(True)

        # Left: square artwork ───────────────────────────────────────────
        if episode.artwork_exists:
            try:
                art: Gtk.Widget = Gtk.Picture.new_for_filename(episode.artwork_path)
                art.set_content_fit(Gtk.ContentFit.COVER)   # type: ignore[attr-defined]
                art.set_can_shrink(True)                     # type: ignore[attr-defined]
            except Exception:
                art = Gtk.Box()
                art.add_css_class("card")
        else:
            art = Gtk.Box()
            art.add_css_class("card")

        art.set_size_request(_BANNER_HEIGHT, _BANNER_HEIGHT)
        art.set_hexpand(False)
        art.set_vexpand(True)
        row.append(art)

        # Right: title + date, centred ───────────────────────────────────
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_box.set_hexpand(True)
        text_box.set_halign(Gtk.Align.FILL)
        text_box.set_valign(Gtk.Align.CENTER)
        text_box.set_margin_start(20)
        text_box.set_margin_end(20)

        tag = Gtk.Label(label="NEW EPISODE")
        tag.add_css_class("cad-new-tag")
        tag.set_halign(Gtk.Align.CENTER)
        text_box.append(tag)

        title_lbl = Gtk.Label(label=episode.display_title)
        title_lbl.set_wrap(True)
        title_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_lbl.set_justify(Gtk.Justification.CENTER)
        title_lbl.set_halign(Gtk.Align.CENTER)
        title_lbl.add_css_class("cad-banner-ep-title")
        text_box.append(title_lbl)

        if episode.pub_date:
            date_lbl = Gtk.Label(label=_format_pub_date(episode.pub_date))
            date_lbl.set_halign(Gtk.Align.CENTER)
            date_lbl.add_css_class("cad-banner-ep-date")
            text_box.append(date_lbl)

        row.append(text_box)
        btn.set_child(row)
        return btn

    def _on_banner_play(self, episode: Episode) -> None:
        """Clicked the episode banner — switch to logo state and play."""
        if self._banner_stack is not None:
            self._banner_stack.set_visible_child_name("logo")
        self._banner_newest_id = None
        self._show_episode_detail(episode)
        self._play_episode(episode)

    def _build_ui(self) -> None:
        self._load_css()
        # Root layout: toolbar view (header + content)
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        # Header bar
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Sidebar toggle
        sidebar_btn = Gtk.ToggleButton(icon_name="sidebar-show-symbolic",
                                       tooltip_text="Show/hide year sidebar")
        sidebar_btn.set_active(True)
        header.pack_start(sidebar_btn)

        # Search entry
        self._search_entry = Gtk.SearchEntry(placeholder_text="Search episodes & tracks…",
                                             hexpand=True, max_width_chars=40)
        self._search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self._search_entry)

        # Volume button
        self._volume_btn = Gtk.VolumeButton()
        self._volume_btn.set_value(1.0)
        self._volume_btn.connect("value-changed", self._on_volume_changed)
        header.pack_end(self._volume_btn)

        # Main content area
        main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_paned.set_vexpand(True)

        # ----- Left: year list -----
        year_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        year_box.set_size_request(120, -1)

        year_label = Gtk.Label(label="<b>Years</b>", use_markup=True,
                               margin_top=12, margin_bottom=6,
                               margin_start=12, margin_end=12)
        year_label.set_halign(Gtk.Align.START)
        year_box.append(year_label)

        year_scroll = Gtk.ScrolledWindow(vexpand=True)
        year_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._year_listbox = Gtk.ListBox()
        self._year_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._year_listbox.add_css_class("navigation-sidebar")
        self._year_listbox.connect("row-activated", self._on_year_selected)
        year_scroll.set_child(self._year_listbox)
        year_box.append(year_scroll)

        main_paned.set_start_child(year_box)
        main_paned.set_position(130)

        # ----- Middle: episode list -----
        ep_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._ep_header = Gtk.Label(label="<b>Episodes</b>", use_markup=True,
                                    margin_top=12, margin_bottom=6,
                                    margin_start=12, margin_end=12)
        self._ep_header.set_halign(Gtk.Align.START)
        ep_box.append(self._ep_header)

        ep_scroll = Gtk.ScrolledWindow(vexpand=True)
        ep_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        ep_scroll.set_size_request(280, -1)

        self._ep_listbox = Gtk.ListBox()
        self._ep_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._ep_listbox.add_css_class("boxed-list")
        self._ep_listbox.connect("row-activated", self._on_ep_list_row_activated)
        ep_scroll.set_child(self._ep_listbox)
        ep_box.append(ep_scroll)

        middle_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        middle_paned.set_start_child(ep_box)
        middle_paned.set_position(320)

        # ----- Right: detail panel -----
        self._detail_panel = self._build_detail_panel()
        middle_paned.set_end_child(self._detail_panel)

        main_paned.set_end_child(middle_paned)

        # ----- Bottom: playback bar -----
        playbar = self._build_playbar()

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(self._build_banner())
        content_box.append(main_paned)
        content_box.append(playbar)

        toolbar_view.set_content(content_box)

        # Wire sidebar toggle
        sidebar_btn.connect("toggled", lambda btn: year_box.set_visible(btn.get_active()))

    def _build_detail_panel(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_size_request(340, -1)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                        margin_top=12, margin_bottom=12,
                        margin_start=16, margin_end=16)

        # Artwork
        self._artwork_image = Gtk.Image()
        self._artwork_image.set_size_request(300, 300)
        self._artwork_image.add_css_class("card")
        inner.append(self._artwork_image)

        # Episode title
        self._detail_title = Gtk.Label(label="Select an episode")
        self._detail_title.set_wrap(True)
        self._detail_title.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._detail_title.add_css_class("title-2")
        self._detail_title.set_halign(Gtk.Align.CENTER)
        self._detail_title.set_justify(Gtk.Justification.CENTER)
        inner.append(self._detail_title)

        # Description
        self._detail_desc = Gtk.Label(label="")
        self._detail_desc.set_wrap(True)
        self._detail_desc.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._detail_desc.add_css_class("body")
        self._detail_desc.set_halign(Gtk.Align.START)
        inner.append(self._detail_desc)

        # Tracklist separator
        sep = Gtk.Separator()
        inner.append(sep)

        track_label = Gtk.Label(label="<b>Tracklist</b>", use_markup=True)
        track_label.set_halign(Gtk.Align.START)
        inner.append(track_label)

        # Tracklist listbox — SINGLE selection so we can highlight the current track
        self._track_listbox = Gtk.ListBox()
        self._track_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._track_listbox.add_css_class("boxed-list")
        self._track_listbox.connect("row-activated", self._on_track_activated)
        inner.append(self._track_listbox)

        scroll.set_child(inner)
        box.append(scroll)
        return box

    def _build_playbar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                      margin_top=8, margin_bottom=8,
                      margin_start=16, margin_end=16)
        bar.add_css_class("toolbar")

        # Now-playing label
        self._now_playing_label = Gtk.Label(label="")
        self._now_playing_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._now_playing_label.add_css_class("caption")
        self._now_playing_label.set_halign(Gtk.Align.CENTER)
        bar.append(self._now_playing_label)

        # Progress row
        progress_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._position_label = Gtk.Label(label="0:00")
        self._position_label.set_size_request(55, -1)
        self._position_label.add_css_class("numeric")
        progress_row.append(self._position_label)

        self._seek_bar = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._seek_bar.set_range(0, 1)
        self._seek_bar.set_hexpand(True)
        self._seek_bar.set_draw_value(False)
        self._seek_bar.connect("change-value", self._on_seek)
        progress_row.append(self._seek_bar)

        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.set_size_request(55, -1)
        self._duration_label.add_css_class("numeric")
        progress_row.append(self._duration_label)

        bar.append(progress_row)

        # Transport buttons
        transport = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        transport.set_halign(Gtk.Align.CENTER)

        self._prev_btn  = Gtk.Button(icon_name="media-skip-backward-symbolic",
                                     tooltip_text="Previous episode")
        self._play_btn  = Gtk.Button(icon_name="media-playback-start-symbolic",
                                     tooltip_text="Play / Pause")
        self._next_btn  = Gtk.Button(icon_name="media-skip-forward-symbolic",
                                     tooltip_text="Next episode")

        self._play_btn.add_css_class("suggested-action")
        self._play_btn.add_css_class("circular")
        for btn in (self._prev_btn, self._play_btn, self._next_btn):
            btn.add_css_class("circular")
            transport.append(btn)

        self._prev_btn.connect("clicked", lambda _: self._prev_episode())
        self._play_btn.connect("clicked", lambda _: self._toggle_play())
        self._next_btn.connect("clicked", lambda _: self._next_episode())

        bar.append(transport)
        return bar

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate_years(self) -> None:
        while self._year_listbox.get_first_child():
            self._year_listbox.remove(self._year_listbox.get_first_child())

        # "Favorites" entry
        fav_row = Gtk.ListBoxRow()
        fav_row._year = "favorites"
        fav_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                           margin_top=6, margin_bottom=6,
                           margin_start=12, margin_end=12)
        fav_icon = Gtk.Image.new_from_icon_name("emblem-favorite-symbolic")
        fav_label = Gtk.Label(label="Favorites")
        fav_label.set_halign(Gtk.Align.START)
        fav_hbox.append(fav_icon)
        fav_hbox.append(fav_label)
        fav_row.set_child(fav_hbox)
        self._year_listbox.append(fav_row)

        # Separator between Favorites and year list
        sep_row = Gtk.ListBoxRow()
        sep_row._year = "__separator__"
        sep_row.set_selectable(False)
        sep_row.set_activatable(False)
        sep_row.set_child(Gtk.Separator())
        self._year_listbox.append(sep_row)

        # "All" entry
        all_row = Gtk.ListBoxRow()
        all_row._year = None
        all_label = Gtk.Label(label="All", margin_top=6, margin_bottom=6,
                              margin_start=12, margin_end=12)
        all_label.set_halign(Gtk.Align.START)
        all_row.set_child(all_label)
        self._year_listbox.append(all_row)

        for year in self._library.years():
            row = Gtk.ListBoxRow()
            row._year = year
            lbl = Gtk.Label(label=str(year), margin_top=6, margin_bottom=6,
                            margin_start=12, margin_end=12)
            lbl.set_halign(Gtk.Align.START)
            row.set_child(lbl)
            self._year_listbox.append(row)

        # Select "All" by default
        self._year_listbox.select_row(all_row)
        self._show_episodes(self._library.episodes)

    def _show_episodes(self, episodes: list[Episode]) -> None:
        self._episode_list = episodes
        self._current_index = -1

        while self._ep_listbox.get_first_child():
            self._ep_listbox.remove(self._ep_listbox.get_first_child())

        for ep in episodes:
            row = Gtk.ListBoxRow()
            row._episode = ep

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                           margin_top=8, margin_bottom=8,
                           margin_start=12, margin_end=12)

            title_lbl = Gtk.Label(label=ep.display_title)
            title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            title_lbl.set_halign(Gtk.Align.START)
            title_lbl.add_css_class("body")

            date_lbl = Gtk.Label(label=ep.pub_date or "")
            date_lbl.set_halign(Gtk.Align.START)
            date_lbl.add_css_class("caption")
            date_lbl.add_css_class("dim-label")

            vbox.append(title_lbl)
            vbox.append(date_lbl)
            row.set_child(vbox)
            self._ep_listbox.append(row)

    def _show_episode_detail(self, episode: Episode) -> None:
        self._current_episode = episode
        self._detail_title.set_label(episode.display_title)
        self._detail_desc.set_label(episode.description or "")

        # Artwork
        if episode.artwork_exists:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    episode.artwork_path, 300, 300, True
                )
                self._artwork_image.set_from_pixbuf(pb)
            except Exception:
                self._artwork_image.set_from_icon_name("audio-x-generic-symbolic")
        else:
            self._artwork_image.set_from_icon_name("audio-x-generic-symbolic")

        # Tracklist
        while self._track_listbox.get_first_child():
            self._track_listbox.remove(self._track_listbox.get_first_child())

        self._track_rows = []
        self._active_track_row = None

        if episode.tracklist:
            # Load all favorited positions for this episode in one query.
            fav_positions = self._favorites.episode_favorite_positions(episode.id)

            for track in episode.tracklist:
                seek_sec = _timestamp_to_seconds(track.timestamp)
                is_fav   = track.position in fav_positions

                row = Gtk.ListBoxRow()
                row._seek_sec = seek_sec
                row.set_activatable(True)
                row.set_tooltip_text(f"Jump to {track.timestamp}")

                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                               margin_top=6, margin_bottom=6,
                               margin_start=12, margin_end=12)

                # Timestamp label
                ts_lbl = Gtk.Label(label=track.timestamp)
                ts_lbl.add_css_class("numeric")
                ts_lbl.add_css_class("dim-label")
                ts_lbl.set_size_request(60, -1)
                ts_lbl.set_halign(Gtk.Align.END)
                ts_lbl.set_valign(Gtk.Align.CENTER)

                # Artist + song title
                info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
                info_box.set_hexpand(True)

                artist_lbl = Gtk.Label(label=track.artist)
                artist_lbl.set_halign(Gtk.Align.START)
                artist_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                artist_lbl.add_css_class("body")

                song_lbl = Gtk.Label(label=track.title)
                song_lbl.set_halign(Gtk.Align.START)
                song_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                song_lbl.add_css_class("caption")
                song_lbl.add_css_class("dim-label")

                info_box.append(artist_lbl)
                info_box.append(song_lbl)

                # Heart toggle button
                heart_btn = Gtk.ToggleButton()
                heart_btn.set_active(is_fav)
                heart_btn.set_icon_name(
                    "emblem-favorite-symbolic" if is_fav else "emblem-favorite-symbolic"
                )
                heart_btn.set_valign(Gtk.Align.CENTER)
                heart_btn.set_has_frame(False)
                heart_btn.set_tooltip_text(
                    "Remove from favorites" if is_fav else "Add to favorites"
                )
                _apply_heart_style(heart_btn, is_fav)
                heart_btn.connect(
                    "toggled",
                    self._on_favorite_toggled,
                    episode,
                    track,
                )

                hbox.append(ts_lbl)
                hbox.append(info_box)
                hbox.append(heart_btn)
                row.set_child(hbox)
                self._track_listbox.append(row)
                self._track_rows.append((seek_sec, row))
        else:
            no_tracks = Gtk.ListBoxRow()
            no_tracks.set_selectable(False)
            no_tracks.set_activatable(False)
            lbl = Gtk.Label(label="No tracklist available",
                            margin_top=8, margin_bottom=8)
            lbl.add_css_class("dim-label")
            no_tracks.set_child(lbl)
            self._track_listbox.append(no_tracks)

    def _show_favorites(self) -> None:
        """Populate the middle panel with a flat list of all favorited tracks."""
        self._episode_list = []
        self._current_index = -1

        while self._ep_listbox.get_first_child():
            self._ep_listbox.remove(self._ep_listbox.get_first_child())

        favorites = self._favorites.get_all()

        if not favorites:
            placeholder = Gtk.ListBoxRow()
            placeholder.set_selectable(False)
            placeholder.set_activatable(False)
            lbl = Gtk.Label(
                label="No favorites yet.\nHeart a track in any episode to save it here.",
                margin_top=16, margin_bottom=16,
                margin_start=12, margin_end=12,
            )
            lbl.set_wrap(True)
            lbl.set_justify(Gtk.Justification.CENTER)
            lbl.add_css_class("dim-label")
            placeholder.set_child(lbl)
            self._ep_listbox.append(placeholder)
            return

        for i, fav in enumerate(favorites):
            row = Gtk.ListBoxRow()
            row._favorite = fav

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                           margin_top=6, margin_bottom=6,
                           margin_start=12, margin_end=8)

            # Text content
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vbox.set_hexpand(True)

            track_lbl = Gtk.Label(label=fav.display_artist_title)
            track_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            track_lbl.set_halign(Gtk.Align.START)
            track_lbl.add_css_class("body")
            vbox.append(track_lbl)

            ep_lbl = Gtk.Label(
                label=f"{fav.episode_title or 'Unknown episode'}  ·  {fav.timestamp}"
            )
            ep_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            ep_lbl.set_halign(Gtk.Align.START)
            ep_lbl.add_css_class("caption")
            ep_lbl.add_css_class("dim-label")
            vbox.append(ep_lbl)

            if fav.pub_date:
                date_lbl = Gtk.Label(label=fav.pub_date)
                date_lbl.set_halign(Gtk.Align.START)
                date_lbl.add_css_class("caption")
                date_lbl.add_css_class("dim-label")
                vbox.append(date_lbl)

            hbox.append(vbox)

            # Unfavorite heart button
            heart_btn = Gtk.Button(icon_name="emblem-favorite-symbolic")
            heart_btn.set_valign(Gtk.Align.CENTER)
            heart_btn.set_has_frame(False)
            heart_btn.add_css_class("circular")
            heart_btn.add_css_class("accent")
            heart_btn.set_tooltip_text("Remove from favorites")
            heart_btn.connect("clicked", lambda _, f=fav: self._unfavorite_from_list(f))
            hbox.append(heart_btn)

            # Up / Down reorder buttons
            btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            btn_box.set_valign(Gtk.Align.CENTER)

            up_btn = Gtk.Button(icon_name="go-up-symbolic")
            up_btn.set_has_frame(False)
            up_btn.add_css_class("circular")
            up_btn.set_sensitive(i > 0)
            up_btn.set_tooltip_text("Move up")
            up_btn.connect("clicked", lambda _, idx=i: self._reorder_favorite(idx, idx - 1))
            btn_box.append(up_btn)

            down_btn = Gtk.Button(icon_name="go-down-symbolic")
            down_btn.set_has_frame(False)
            down_btn.add_css_class("circular")
            down_btn.set_sensitive(i < len(favorites) - 1)
            down_btn.set_tooltip_text("Move down")
            down_btn.connect("clicked", lambda _, idx=i: self._reorder_favorite(idx, idx + 1))
            btn_box.append(down_btn)

            hbox.append(btn_box)
            row.set_child(hbox)
            self._ep_listbox.append(row)

    def _on_favorite_row_activated(self, _listbox, row) -> None:
        """A favorite track row was clicked — navigate to its episode and seek."""
        fav: Favorite = getattr(row, "_favorite", None)
        if fav is None:
            return

        ep = self._library.episode_by_id(fav.episode_id)
        if ep is None:
            self._show_toast("Episode not in local library")
            return

        self._show_episode_detail(ep)
        seek_sec = _timestamp_to_seconds(fav.timestamp)

        if self._player.state == PlayerState.STOPPED:
            self._play_episode(ep)
            GLib.timeout_add(300, lambda: self._player.seek(seek_sec) or False)
        else:
            # If a different episode is already playing, switch to the new one
            if self._current_episode and self._current_episode.id != ep.id:
                self._play_episode(ep)
                GLib.timeout_add(300, lambda: self._player.seek(seek_sec) or False)
            else:
                self._player.seek(seek_sec)

        self._current_episode = ep

    def _unfavorite_from_list(self, fav) -> None:
        """Remove a track from favorites directly from the favorites panel."""
        self._favorites.toggle(fav.episode_id, fav.position)
        self._show_favorites()

    def _reorder_favorite(self, from_idx: int, to_idx: int) -> None:
        """Move a favorite up or down and refresh the list."""
        self._favorites.reorder(from_idx, to_idx)
        self._show_favorites()

    def _show_track_results(self, results) -> None:
        """Display individual track search results in the episode list panel."""
        self._episode_list = []
        self._current_index = -1

        while self._ep_listbox.get_first_child():
            self._ep_listbox.remove(self._ep_listbox.get_first_child())

        for result in results:
            track = result.track
            episode = result.episode

            row = Gtk.ListBoxRow()
            row._track_result = result

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                           margin_top=8, margin_bottom=8,
                           margin_start=12, margin_end=8)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vbox.set_hexpand(True)

            label_text = f"{track.artist} — {track.title}" if track.artist else track.title
            track_lbl = Gtk.Label(label=label_text)
            track_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            track_lbl.set_halign(Gtk.Align.START)
            track_lbl.add_css_class("body")
            vbox.append(track_lbl)

            ep_lbl = Gtk.Label(
                label=f"{episode.display_title}  ·  {track.timestamp}"
            )
            ep_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            ep_lbl.set_halign(Gtk.Align.START)
            ep_lbl.add_css_class("caption")
            ep_lbl.add_css_class("dim-label")
            vbox.append(ep_lbl)

            hbox.append(vbox)

            play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            play_btn.add_css_class("circular")
            play_btn.set_valign(Gtk.Align.CENTER)
            play_btn.set_tooltip_text(f"Play at {track.timestamp}")
            play_btn.connect("clicked", lambda _, r=result: self._play_track_result(r))
            hbox.append(play_btn)

            row.set_child(hbox)
            self._ep_listbox.append(row)

    def _play_track_result(self, result) -> None:
        """Show the episode detail and seek to the track's timestamp."""
        episode = result.episode
        seek_sec = _timestamp_to_seconds(result.track.timestamp)
        self._show_episode_detail(episode)
        if (self._player.state == PlayerState.STOPPED
                or (self._current_episode and self._current_episode.id != episode.id)):
            self._play_episode(episode)
            GLib.timeout_add(300, lambda: self._player.seek(seek_sec) or False)
        else:
            self._player.seek(seek_sec)
        self._current_episode = episode

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_year_selected(self, _listbox, row) -> None:
        # Clear any active search when switching views via the sidebar
        self._search_entry.set_text("")
        self._track_search_mode = False
        year = row._year
        if year == "favorites":
            self._favorites_mode = True
            self._ep_header.set_markup("<b>Favorites</b>")
            self._show_favorites()
        elif year == "__separator__":
            pass  # non-selectable, but guard just in case
        else:
            self._favorites_mode = False
            self._ep_header.set_markup("<b>Episodes</b>")
            if year is None:
                self._show_episodes(self._library.episodes)
            else:
                self._show_episodes(self._library.episodes_for_year(year))

    def _on_ep_list_row_activated(self, listbox, row) -> None:
        if self._favorites_mode:
            self._on_favorite_row_activated(listbox, row)
        elif self._track_search_mode:
            result = getattr(row, "_track_result", None)
            if result is not None:
                self._play_track_result(result)
        else:
            self._on_episode_selected(listbox, row)

    def _on_episode_selected(self, _listbox, row) -> None:
        ep: Episode = row._episode
        idx = self._episode_list.index(ep) if ep in self._episode_list else -1
        self._current_index = idx
        self._show_episode_detail(ep)
        self._play_episode(ep)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip()
        if not query:
            self._track_search_mode = False
            if not self._favorites_mode:
                self._ep_header.set_markup("<b>Episodes</b>")
                self._show_episodes(self._library.episodes)
            return
        track_results = self._library.search_tracks(query)
        if track_results:
            self._track_search_mode = True
            self._favorites_mode = False
            self._ep_header.set_markup(f"<b>Tracks ({len(track_results)})</b>")
            self._show_track_results(track_results)
        else:
            self._track_search_mode = False
            self._favorites_mode = False
            self._ep_header.set_markup("<b>Episodes</b>")
            self._show_episodes(self._library.search(query))

    def _on_volume_changed(self, _btn, value: float) -> None:
        self._player.set_volume(value)

    def _on_favorite_toggled(self, btn: Gtk.ToggleButton, episode: Episode, track) -> None:
        """Heart button toggled — save or remove the track from favorites."""
        # Relative audio/artwork paths are what FavoritesStore expects
        # (it will make them absolute internally).
        from pathlib import Path as _Path
        archive_parent = self._library.archive_root.parent

        def _rel(abs_path: str) -> str:
            try:
                return str(_Path(abs_path).relative_to(archive_parent))
            except ValueError:
                return abs_path

        now_favorite = self._favorites.toggle(
            episode_id=episode.id,
            position=track.position,
            artist=track.artist,
            title=track.title,
            timestamp=track.timestamp,
            episode_title=episode.display_title,
            pub_date=episode.pub_date,
            audio_path=_rel(episode.audio_path),
            artwork_path=_rel(episode.artwork_path) if episode.artwork_path else "",
        )

        _apply_heart_style(btn, now_favorite)
        btn.set_tooltip_text(
            "Remove from favorites" if now_favorite else "Add to favorites"
        )

        # If the favorites panel is currently open, refresh it live.
        if self._favorites_mode:
            self._show_favorites()

    def _on_seek(self, _scale, _scroll_type, value: float) -> bool:
        # value is 0..1 normalised — multiply by duration to get seconds
        _pos, dur = self._player.get_position()
        if dur > 0:
            self._player.seek(value * dur)
        return False

    def _on_track_activated(self, _listbox, row: Gtk.ListBoxRow) -> None:
        """Seek to the track's start time when a tracklist row is clicked."""
        seek_sec = getattr(row, "_seek_sec", None)
        if seek_sec is None:
            return
        if self._player.state == PlayerState.STOPPED and self._current_episode:
            # Start playback first, then seek once the pipeline is ready
            self._play_episode(self._current_episode)
            # Small delay to let GStreamer reach PLAYING before seeking
            GLib.timeout_add(300, lambda: self._player.seek(seek_sec) or False)
        else:
            self._player.seek(seek_sec)

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _play_episode(self, episode: Episode) -> None:
        if not Path(episode.audio_path).exists():
            self._show_toast("Audio file not found")
            return
        self._player.play(episode.audio_path)
        self._now_playing_label.set_label(f"▶  {episode.display_title}")
        self._play_btn.set_icon_name("media-playback-pause-symbolic")
        # Switch banner back to logo once the newest episode is played.
        self._listened_ids.add(episode.id)
        if (self._banner_stack is not None
                and self._banner_newest_id is not None
                and episode.id == self._banner_newest_id):
            self._banner_stack.set_visible_child_name("logo")
            self._banner_newest_id = None

    def _toggle_play(self) -> None:
        if self._player.state == PlayerState.STOPPED:
            if self._current_episode:
                self._play_episode(self._current_episode)
        else:
            self._player.toggle_pause()

    def _prev_episode(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            ep = self._episode_list[self._current_index]
            self._show_episode_detail(ep)
            self._play_episode(ep)
            # Sync list selection
            child = self._ep_listbox.get_row_at_index(self._current_index)
            if child:
                self._ep_listbox.select_row(child)

    def _next_episode(self) -> None:
        if self._current_index < len(self._episode_list) - 1:
            self._current_index += 1
            ep = self._episode_list[self._current_index]
            self._show_episode_detail(ep)
            self._play_episode(ep)
            child = self._ep_listbox.get_row_at_index(self._current_index)
            if child:
                self._ep_listbox.select_row(child)

    # ------------------------------------------------------------------
    # Player callbacks
    # ------------------------------------------------------------------

    def _connect_player(self) -> None:
        self._player.on_state_changed(self._on_player_state)
        self._player.on_position_changed(self._on_player_position)
        self._player.on_eos(self._on_player_eos)
        self._player.on_error(self._on_player_error)

    def _on_player_state(self, state: str) -> None:
        icon = {
            PlayerState.PLAYING: "media-playback-pause-symbolic",
            PlayerState.PAUSED:  "media-playback-start-symbolic",
            PlayerState.STOPPED: "media-playback-start-symbolic",
        }.get(state, "media-playback-start-symbolic")
        self._play_btn.set_icon_name(icon)

    def _on_player_position(self, pos_sec: int, dur_sec: int) -> None:
        self._position_label.set_label(format_time(pos_sec))
        self._duration_label.set_label(format_time(dur_sec))
        if dur_sec > 0:
            self._seek_bar.set_value(pos_sec / dur_sec)
        self._update_track_highlight(pos_sec)

    def _update_track_highlight(self, pos_sec: int) -> None:
        """Select the tracklist row whose window contains pos_sec."""
        if not self._track_rows:
            return

        # Walk forward: the current track is the last one whose start ≤ pos_sec.
        current_row: Gtk.ListBoxRow | None = None
        for seek_sec, row in self._track_rows:
            if seek_sec <= pos_sec:
                current_row = row
            else:
                break  # list is in ascending order; no point continuing

        if current_row is self._active_track_row:
            return  # nothing changed

        self._active_track_row = current_row
        self._track_listbox.select_row(current_row)

        # Scroll the highlighted row into view
        if current_row is not None:
            current_row.grab_focus()

    def _on_player_eos(self) -> None:
        self._next_episode()

    def _on_player_error(self, msg: str) -> None:
        self._show_toast(f"Playback error: {msg}")

    # ------------------------------------------------------------------
    # Toast notifications
    # ------------------------------------------------------------------

    def _show_toast(self, message: str) -> None:
        toast = Adw.Toast(title=message, timeout=3)
        # Adw.ApplicationWindow has a toast overlay we can use
        overlay = Adw.ToastOverlay()
        overlay.add_toast(toast)
