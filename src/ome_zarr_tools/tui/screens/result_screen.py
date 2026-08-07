"""Command Result screen (spec 004 US7): where Run navigates immediately.

Unlike every other command screen, this one does *not* reuse
``shared_bindings()`` wholesale -- there's nothing to Run or Copy here, so
only the shortcuts that actually do something (Back to form, Log, Cancel)
are bound, to avoid dead footer entries (constitution Principle I).
"""

from __future__ import annotations

from collections.abc import Callable

import click
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from ome_zarr_tools.tui.execution import ExecutionResult
from ome_zarr_tools.tui.fields import build_identity_frame
from ome_zarr_tools.tui.status import StatusPanel


class CommandResultScreen(Screen[None]):
    """Base: identity frame + pending progress indicator, swapping to a
    success/failure indicator + command-specific content once finished."""

    BINDINGS = [
        Binding("escape", "back", "Back to form"),
        Binding("f8", "toggle_log", "Log"),
        Binding("ctrl+c", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    #bottom-bar {
        dock: bottom;
        height: auto;
    }
    """

    def __init__(self, command: click.Command) -> None:
        super().__init__()
        self.command = command
        self._finished = False
        self._status_panel = StatusPanel()
        self._outcome_label = Label("", id="outcome-label")
        self._content_container = Vertical(id="result-content")

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            yield self._outcome_label
            yield self._content_container
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_mount(self) -> None:
        self._outcome_label.display = False

    def compose_result_content(self) -> ComposeResult:
        """Override in subclasses for finished-state, command-specific widgets."""
        yield from ()

    def begin(self) -> tuple[Callable[[int, int], None], Callable[[str], None]]:
        """Call once this screen is pushed; returns the (on_progress, on_log)
        callables to pass into ``run_in_background``/``run_command``."""
        self._status_panel.start()
        return self._status_panel.update_progress, self._status_panel.append_log

    async def finish(self, result: ExecutionResult) -> None:
        """The ``on_done`` callback: flips this screen from pending to finished."""
        self._finished = True
        self._status_panel.stop()
        self._outcome_label.display = True
        if result.succeeded:
            self._outcome_label.update(f"[green]✓ {self.command.name} succeeded.[/]")
        else:
            self._outcome_label.update(f"[red]✗ {self.command.name} failed: {result.error}[/]")
        await self._content_container.remove_children()
        await self._content_container.mount_all(list(self.compose_result_content()))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_toggle_log(self) -> None:
        self._status_panel.toggle_log()

    def action_cancel(self) -> None:
        self.app.exit(result=None)


class GenericResultScreen(CommandResultScreen):
    """Result screen for commands without their own specialized screen
    (from_images, extract, apply_mask) -- no content beyond the shared log."""
