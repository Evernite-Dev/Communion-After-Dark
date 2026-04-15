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
from pathlib import Path
from typing import TYPE_CHECKING

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gtk, GdkPixbuf, GLib, Gio, Pango

from .favorites import Favorite, FavoritesStore
from .library import Episode, Library
from .player_backend import AudioPlayer, PlayerState, format_time

if TYPE_CHECKING:
    pass

APP_ID = "com.communionafterdark.CadPlayer"


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

    def _build_ui(self) -> None:
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

        for fav in favorites:
            row = Gtk.ListBoxRow()
            row._favorite = fav

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                           margin_top=8, margin_bottom=8,
                           margin_start=12, margin_end=12)

            # Artist — Song title
            track_lbl = Gtk.Label(label=fav.display_artist_title)
            track_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            track_lbl.set_halign(Gtk.Align.START)
            track_lbl.add_css_class("body")
            vbox.append(track_lbl)

            # Episode title @ timestamp
            ep_lbl = Gtk.Label(
                label=f"{fav.episode_title or 'Unknown episode'}  ·  {fav.timestamp}"
            )
            ep_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            ep_lbl.set_halign(Gtk.Align.START)
            ep_lbl.add_css_class("caption")
            ep_lbl.add_css_class("dim-label")
            vbox.append(ep_lbl)

            # Date favorited (very small)
            if fav.pub_date:
                date_lbl = Gtk.Label(label=fav.pub_date)
                date_lbl.set_halign(Gtk.Align.START)
                date_lbl.add_css_class("caption")
                date_lbl.add_css_class("dim-label")
                vbox.append(date_lbl)

            row.set_child(vbox)
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

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_year_selected(self, _listbox, row) -> None:
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
            self._show_episodes(self._library.episodes)
        else:
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
