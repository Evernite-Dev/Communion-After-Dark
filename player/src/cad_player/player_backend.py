"""
GStreamer-based audio playback backend.

Wraps a GStreamer playbin pipeline. Designed to be used from the GTK4 main
thread; all signal emissions happen on the GLib main loop via idle_add.
"""

from __future__ import annotations

import logging
from typing import Callable

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

log = logging.getLogger(__name__)

Gst.init(None)


class PlayerState:
    STOPPED  = "stopped"
    PLAYING  = "playing"
    PAUSED   = "paused"


class AudioPlayer:
    def __init__(self) -> None:
        self._pipeline: Gst.Element = Gst.ElementFactory.make("playbin", "player")
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        self.state: str = PlayerState.STOPPED

        # Callbacks registered by the UI
        self._on_state_changed: Callable[[str], None] | None = None
        self._on_position_changed: Callable[[int, int], None] | None = None  # (pos_sec, dur_sec)
        self._on_eos: Callable[[], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        # Position polling
        self._poll_id: int | None = None

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    def play(self, uri: str) -> None:
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", _to_uri(uri))
        self._pipeline.set_state(Gst.State.PLAYING)
        self.state = PlayerState.PLAYING
        self._start_polling()
        self._emit_state()

    def pause(self) -> None:
        if self.state == PlayerState.PLAYING:
            self._pipeline.set_state(Gst.State.PAUSED)
            self.state = PlayerState.PAUSED
            self._emit_state()

    def resume(self) -> None:
        if self.state == PlayerState.PAUSED:
            self._pipeline.set_state(Gst.State.PLAYING)
            self.state = PlayerState.PLAYING
            self._emit_state()

    def toggle_pause(self) -> None:
        if self.state == PlayerState.PLAYING:
            self.pause()
        elif self.state == PlayerState.PAUSED:
            self.resume()

    def stop(self) -> None:
        self._pipeline.set_state(Gst.State.NULL)
        self.state = PlayerState.STOPPED
        self._stop_polling()
        self._emit_state()

    def seek(self, position_sec: float) -> None:
        ns = int(position_sec * Gst.SECOND)
        self._pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            ns,
        )

    def get_position(self) -> tuple[int, int]:
        """Returns (position_sec, duration_sec)."""
        ok_pos, pos = self._pipeline.query_position(Gst.Format.TIME)
        ok_dur, dur = self._pipeline.query_duration(Gst.Format.TIME)
        pos_sec = int(pos / Gst.SECOND) if ok_pos and pos >= 0 else 0
        dur_sec = int(dur / Gst.SECOND) if ok_dur and dur >= 0 else 0
        return pos_sec, dur_sec

    def set_volume(self, volume: float) -> None:
        """Volume in range 0.0–1.0."""
        self._pipeline.set_property("volume", max(0.0, min(1.0, volume)))

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_state_changed(self, cb: Callable[[str], None]) -> None:
        self._on_state_changed = cb

    def on_position_changed(self, cb: Callable[[int, int], None]) -> None:
        self._on_position_changed = cb

    def on_eos(self, cb: Callable[[], None]) -> None:
        self._on_eos = cb

    def on_error(self, cb: Callable[[str], None]) -> None:
        self._on_error = cb

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit_state(self) -> None:
        if self._on_state_changed:
            self._on_state_changed(self.state)

    def _start_polling(self) -> None:
        self._stop_polling()
        self._poll_id = GLib.timeout_add(500, self._poll_position)

    def _stop_polling(self) -> None:
        if self._poll_id is not None:
            GLib.source_remove(self._poll_id)
            self._poll_id = None

    def _poll_position(self) -> bool:
        if self.state != PlayerState.PLAYING:
            return False
        pos, dur = self.get_position()
        if self._on_position_changed:
            self._on_position_changed(pos, dur)
        return True  # keep firing

    def _on_bus_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        t = message.type
        if t == Gst.MessageType.EOS:
            self.state = PlayerState.STOPPED
            self._stop_polling()
            self._emit_state()
            if self._on_eos:
                GLib.idle_add(self._on_eos)
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            log.error("GStreamer error: %s (%s)", err, debug)
            self.state = PlayerState.STOPPED
            self._stop_polling()
            self._emit_state()
            if self._on_error:
                GLib.idle_add(self._on_error, str(err))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_uri(path: str) -> str:
    if path.startswith(("file://", "http://", "https://")):
        return path
    from pathlib import Path
    return Path(path).as_uri()


def format_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
