"""Textual TUI for ``interactive --tui``.

Two screens: a Command Menu (pick a subcommand) and a Command Form (edit all of
that command's fields together). **No button.** A persistent footer shows
Run/Copy/Copy-and-exit/toggle-log shortcuts (F5/F6/F7/F8). Running executes
immediately on Run rather than behind a confirmation dialog (FR-005); the
equivalent direct-CLI invocation is computed on demand for Copy/Copy-and-exit,
not rendered as a live preview (spec 003 US2). Pressing Run executes the
command in a worker thread (``tui/execution.py``) without the app exiting --
it stays open to show live status/log (User Story 5) until the user exits it
themselves.
"""

from __future__ import annotations

from collections.abc import Callable

import click
from rich.console import Group
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Checkbox, Footer, Header, Input, OptionList, Select
from textual.widgets.option_list import Option

from ome_zarr_tools.tui.execution import ExecutionResult, run_command
from ome_zarr_tools.tui.fields import (
    FIELD_GAP_CSS,
    FieldSpec,
    build_field_frames,
    build_field_spec,
    build_identity_frame,
    command_description,
    field_label,
    is_required,
    refresh_required_subtitle,
    widget_value_to_tokens,
)
from ome_zarr_tools.tui.logo import Logo
from ome_zarr_tools.tui.screens.config_screen import ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectScreen
from ome_zarr_tools.tui.screens.metadata_screen import FixMetadataScreen, MigrateScreen
from ome_zarr_tools.tui.screens.result_screen import GenericResultScreen
from ome_zarr_tools.tui.shortcuts import shared_bindings
from ome_zarr_tools.tui.status import StatusPanel

# Commands with their own specialized screen instead of the generic CommandFormScreen.
_SPECIALIZED_SCREENS: dict[str, Callable[[click.Command], Screen[None]]] = {
    "fix_metadata": FixMetadataScreen,
    "migrate": MigrateScreen,
    "inspect": InspectScreen,
    "config": ConfigScreen,
}


def _menu_option_prompt(name: str, command: click.Command) -> Group:
    """A 3-line Rich prompt for one command's OptionList row (spec 004 US1):
    name, the command's existing one-line help text (never duplicated,
    blank if the command has none), and a blank spacing line."""
    return Group(
        Text(f"▎ {name}", style="bold"),
        Text(
            f"  {command_description(command)}",
            style="dim",
            no_wrap=True,
            overflow="crop",
        ),
        Text(""),
    )


class CommandMenuScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    CommandMenuScreen > OptionList > .option-list--option {
        color: #d4af37;
    }
    """

    def __init__(self, commands: dict[str, click.Command]) -> None:
        super().__init__()
        self.commands = commands

    def compose(self) -> ComposeResult:
        yield Header()
        yield Logo()
        yield OptionList(
            *[
                Option(_menu_option_prompt(name, self.commands[name]), id=name)
                for name in sorted(self.commands)
            ]
        )
        yield Footer()

    def on_resize(self, event: events.Resize) -> None:
        self.query_one(Logo).set_visible_for_size(*event.size)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        name = str(event.option.id)
        command = self.commands[name]
        screen_cls = _SPECIALIZED_SCREENS.get(name)
        if screen_cls is not None:
            self.app.push_screen(screen_cls(command))
        else:
            self.app.push_screen(CommandFormScreen(command))

    def action_cancel(self) -> None:
        self.app.exit(result=None)


class CommandFormScreen(Screen[None]):
    """The generic form for any command without its own specialized screen.

    ``fix_metadata``/``migrate`` (US4), ``inspect`` (US6), and ``config`` (US7)
    each get their own screen instead of this one -- see ``tui/screens/``.
    """

    BINDINGS = [*shared_bindings(), Binding("f4", "restore_defaults", "Restore Defaults")]

    DEFAULT_CSS = (
        """
    #bottom-bar {
        dock: bottom;
        height: auto;
    }
    """
        + FIELD_GAP_CSS
    )

    def __init__(self, command: click.Command) -> None:
        super().__init__()
        self.command = command
        self._field_specs: list[FieldSpec] = []
        self._required_frame: Vertical | None = None
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._pending_result: GenericResultScreen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            self._field_specs = [build_field_spec(param) for param in self.command.params]
            for frame in build_field_frames(self._field_specs):
                if frame.id == "required-frame":
                    self._required_frame = frame
                yield frame
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh_required_subtitle()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh_required_subtitle()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh_required_subtitle()

    def _refresh_required_subtitle(self) -> None:
        if self._required_frame is not None:
            refresh_required_subtitle(self._required_frame, self._field_specs)

    def _build_tokens(self) -> list[str] | None:
        """Return the current field values as CLI tokens, or None if a required field is empty."""
        tokens: list[str] = []
        for param, spec in zip(self.command.params, self._field_specs, strict=True):
            value_tokens = widget_value_to_tokens(param, spec.widget)
            if is_required(param) and not value_tokens:
                return None
            tokens.extend(value_tokens)
        return tokens

    def _invocation_text(self) -> str:
        tokens: list[str] = []
        for param, spec in zip(self.command.params, self._field_specs, strict=True):
            tokens.extend(widget_value_to_tokens(param, spec.widget))
        return f"ome-zarr-tools {self.command.name} {' '.join(tokens)}".strip()

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)
        self._status_panel.append_log(line)

    def action_run(self) -> None:
        tokens = self._build_tokens()
        if tokens is None:
            for param, spec in zip(self.command.params, self._field_specs, strict=True):
                if is_required(param) and not widget_value_to_tokens(param, spec.widget):
                    spec.widget.focus()
                    self.notify(f"{field_label(param)} is required", severity="error")
                    return
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        for spec in self._field_specs:
            spec.widget.disabled = True

        result_screen = GenericResultScreen(self.command)
        self._pending_result = result_screen
        self.app.push_screen(result_screen)
        on_progress, on_log = result_screen.begin()

        async def _on_done(result: ExecutionResult) -> None:
            self._pending_result = None
            for spec in self._field_specs:
                spec.widget.disabled = False
            await result_screen.finish(result)

        run_command(
            self.app,
            self.command,
            tokens,
            _on_done,
            on_progress=on_progress,
            on_log=on_log,
        )

    def action_copy(self) -> None:
        invocation = self._invocation_text()
        self.app.copy_to_clipboard(invocation)
        self._append_log(f"Copied: {invocation}")
        self.notify("Copied to clipboard (and logged).")

    def action_copy_and_exit(self) -> None:
        self.action_copy()
        self.app.exit(result=self._invocation_text())

    def action_toggle_log(self) -> None:
        self._status_panel.toggle_log()

    async def action_restore_defaults(self) -> None:
        if self._pending_result is not None:
            return
        await self.app.switch_screen(CommandFormScreen(self.command))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.exit(result=None)


class InteractiveTUIApp(App[str | None]):
    """Full-screen interface for `interactive --tui`. Commands run in-app; see tui/execution.py."""

    TITLE = "OME-Zarr Tools"

    DEFAULT_CSS = FIELD_GAP_CSS
    """App-wide fallback so ``.field-gap`` (spec 004 US2) resolves for every
    screen using ``build_field_frames()``, even those without their own local
    copy of this rule -- ``CommandFormScreen``/``FixMetadataConfirmScreen``
    additionally declare it themselves so it also resolves in isolation
    (e.g. under a test harness that doesn't wrap screens in this App)."""

    def __init__(self, commands: dict[str, click.Command]) -> None:
        super().__init__()
        self.commands = commands

    def on_mount(self) -> None:
        self.push_screen(CommandMenuScreen(self.commands))
