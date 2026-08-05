"""Live status indicator (ProgressBar/Sparkline) + toggleable Command Log (FR-014/FR-015).

Mounted into every command's screen (CommandFormScreen, metadata_screen.py's
screens, config_screen.py, inspect_screen.py) inside a "bottom-bar" wrapper
docked to the bottom of the screen, directly above the footer, so it's always
visible without scrolling (see each screen's ``compose()``: ``StatusPanel``
itself does *not* dock -- it relies on that wrapper, since a widget can't
usefully self-dock to the same edge as ``Footer``'s own dock without the two
overlapping). Driven by ``tui/execution.py``'s ``on_progress``/``on_log``
callbacks plus the screen's own ``start()``/``stop()`` calls around a run:
hidden while idle, an animated ``Sparkline`` while running with no
quantifiable progress yet (anchored to the bottom of its own row via
``align-vertical: bottom``), switching to a ``ProgressBar`` the first time a
real ``(done, total)`` update arrives, and hidden again once the run finishes
(data-model.md § Status Indicator).
"""

from __future__ import annotations

import random

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.timer import Timer
from textual.widgets import ProgressBar, RichLog, Sparkline


class StatusPanel(Vertical):
    """One per screen. Call `start()` when a run begins, `stop()` when it ends."""

    DEFAULT_CSS = """
    StatusPanel {
        height: auto;
    }
    StatusPanel #status-sparkline {
        align-vertical: bottom;
    }
    StatusPanel #status-progress {
        width: 1fr;
    }
    StatusPanel #status-progress #bar {
        width: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._sparkline: Sparkline = Sparkline([0.0] * 20, id="status-sparkline")
        self._progress: ProgressBar = ProgressBar(id="status-progress")
        self._log: RichLog = RichLog(id="status-log", max_lines=500)
        self._quantified = False
        self._animation_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield self._sparkline
        yield self._progress
        yield self._log

    def on_mount(self) -> None:
        self._sparkline.display = False
        self._progress.display = False
        self._log.display = False

    def _animate_sparkline(self) -> None:
        if self._quantified:
            return
        data = list(self._sparkline.data or [])
        self._sparkline.data = [*data[1:], random.random()]

    def start(self) -> None:
        """Call when a run begins: show the (indeterminate) sparkline and start animating it."""
        self._quantified = False
        self._progress.display = False
        self._sparkline.display = True
        if self._animation_timer is None:
            self._animation_timer = self.set_interval(0.2, self._animate_sparkline)

    def stop(self) -> None:
        """Call when a run finishes (success or failure): hide the status indicator."""
        if self._animation_timer is not None:
            self._animation_timer.stop()
            self._animation_timer = None
        self._sparkline.display = False
        self._progress.display = False
        self._quantified = False

    def update_progress(self, done: int, total: int) -> None:
        if not self._quantified:
            self._quantified = True
            self._sparkline.display = False
            self._progress.display = True
        self._progress.total = total
        self._progress.progress = done

    def append_log(self, line: str) -> None:
        self._log.write(line)

    def toggle_log(self) -> None:
        self._log.display = not self._log.display
