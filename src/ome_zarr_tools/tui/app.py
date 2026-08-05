"""Textual TUI for ``interactive --tui``.

Two screens: a Command Menu (pick a subcommand) and a Command Form (edit all of
that command's fields together). **No button.** A persistent footer shows
Run/Copy/Copy-and-exit/toggle-log shortcuts (F5/F6/F7/F8). The equivalent
direct-CLI invocation is always visible, recomputed on every field edit --
that visibility, not a confirmation dialog, is what FR-005 relies on. Pressing
Run executes the command in a worker thread (``tui/execution.py``) without the
app exiting -- it stays open to show live status/log (User Story 5) until the
user exits it themselves.
"""

from __future__ import annotations

import click
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList
from textual.widgets.option_list import Option

from ome_zarr_tools.tui.execution import ExecutionResult, run_command
from ome_zarr_tools.tui.fields import (
    build_autocomplete,
    build_field_widget,
    field_label,
    is_required,
    widget_value_to_tokens,
)
from ome_zarr_tools.tui.screens.config_screen import ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectScreen
from ome_zarr_tools.tui.screens.metadata_screen import FixMetadataScreen, MigrateScreen
from ome_zarr_tools.tui.status import StatusPanel

# Commands with their own specialized screen instead of the generic CommandFormScreen.
_SPECIALIZED_SCREENS: dict[str, type[Screen[None]]] = {
    "fix_metadata": FixMetadataScreen,
    "migrate": MigrateScreen,
    "inspect": InspectScreen,
    "config": ConfigScreen,
}


class CommandMenuScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
    ]

    def __init__(self, commands: dict[str, click.Command]) -> None:
        super().__init__()
        self.commands = commands

    def compose(self) -> ComposeResult:
        yield Header()
        yield OptionList(*[Option(name, id=name) for name in sorted(self.commands)])
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        name = str(event.option.id)
        screen_cls = _SPECIALIZED_SCREENS.get(name)
        if screen_cls is not None:
            self.app.push_screen(screen_cls())
        else:
            self.app.push_screen(CommandFormScreen(self.commands[name]))

    def action_cancel(self) -> None:
        self.app.exit(result=None)


class CommandFormScreen(Screen[None]):
    """The generic form for any command without its own specialized screen.

    ``fix_metadata``/``migrate`` (US4), ``inspect`` (US6), and ``config`` (US7)
    each get their own screen instead of this one -- see ``tui/screens/``.
    """

    BINDINGS = [
        Binding("f5", "run", "Run"),
        Binding("f6", "copy", "Copy"),
        Binding("f7", "copy_and_exit", "Copy & exit"),
        Binding("f8", "toggle_log", "Log"),
        Binding("escape", "back", "Back to menu"),
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
        self._field_widgets: dict[str, object] = {}
        self._log_lines: list[str] = []
        self._invocation_label = Label(id="invocation")
        self._status_panel = StatusPanel()

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            for param in self.command.params:
                label = field_label(param) + (" *" if is_required(param) else "")
                yield Label(label)
                widget = build_field_widget(param)
                self._field_widgets[param.name] = widget
                yield widget
                autocomplete = build_autocomplete(param, widget)
                if autocomplete is not None:
                    yield autocomplete
            yield self._invocation_label
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_mount(self) -> None:
        self._refresh_invocation()

    def on_input_changed(self, event) -> None:  # noqa: ANN001
        self._refresh_invocation()

    def on_checkbox_changed(self, event) -> None:  # noqa: ANN001
        self._refresh_invocation()

    def on_select_changed(self, event) -> None:  # noqa: ANN001
        self._refresh_invocation()

    def _build_tokens(self) -> list[str] | None:
        """Return the current field values as CLI tokens, or None if a required field is empty."""
        tokens: list[str] = []
        for param in self.command.params:
            widget = self._field_widgets[param.name]
            value_tokens = widget_value_to_tokens(param, widget)  # type: ignore[arg-type]
            if is_required(param) and not value_tokens:
                return None
            tokens.extend(value_tokens)
        return tokens

    def _invocation_text(self) -> str:
        tokens: list[str] = []
        for param in self.command.params:
            widget = self._field_widgets[param.name]
            tokens.extend(widget_value_to_tokens(param, widget))  # type: ignore[arg-type]
        return f"ome-zarr-tools {self.command.name} {' '.join(tokens)}".strip()

    def _refresh_invocation(self) -> None:
        self._invocation_label.update(f"$ {self._invocation_text()}")

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)

    def action_run(self) -> None:
        tokens = self._build_tokens()
        if tokens is None:
            for param in self.command.params:
                if is_required(param) and not widget_value_to_tokens(
                    param,
                    self._field_widgets[param.name],  # type: ignore[arg-type]
                ):
                    widget = self._field_widgets[param.name]
                    widget.focus()  # type: ignore[attr-defined]
                    self.notify(f"{field_label(param)} is required", severity="error")
                    return
            return
        for widget in self._field_widgets.values():
            widget.disabled = True  # type: ignore[attr-defined]
        self._status_panel.start()
        run_command(
            self.app,
            self.command,
            tokens,
            self._on_execution_done,
            on_progress=self._status_panel.update_progress,
            on_log=self._status_panel.append_log,
        )

    def _on_execution_done(self, result: ExecutionResult) -> None:
        self._status_panel.stop()
        if result.succeeded:
            self._append_log(f"{self.command.name} succeeded.")
            self.notify(f"{self.command.name} succeeded.")
        else:
            self._append_log(f"{self.command.name} failed: {result.error}")
            self.notify(f"{self.command.name} failed: {result.error}", severity="error")

    def action_copy(self) -> None:
        invocation = self._invocation_text()
        self.app.copy_to_clipboard(invocation)
        self._append_log(f"Copied: {invocation}")
        self.notify("Copied to clipboard (and logged).")

    def action_copy_and_exit(self) -> None:
        self.action_copy()
        self.app.exit(result=None)

    def action_toggle_log(self) -> None:
        self._status_panel.toggle_log()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.exit(result=None)


class InteractiveTUIApp(App[None]):
    """Full-screen interface for `interactive --tui`. Commands run in-app; see tui/execution.py."""

    TITLE = "OME-Zarr Tools"

    def __init__(self, commands: dict[str, click.Command]) -> None:
        super().__init__()
        self.commands = commands

    def on_mount(self) -> None:
        self.push_screen(CommandMenuScreen(self.commands))
