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
from textual.widgets import Checkbox, Footer, Header, Input, OptionList, Select, Static
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
            style="#7f9cae",
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
    #unrecognized-keys-warning {
        color: $warning;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        commands: dict[str, click.Command],
        default_map: dict[str, dict[str, str]] | None = None,
        unrecognized: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.commands = commands
        # `is None` (not `or`): an empty-but-given container must keep its own
        # identity, since `InteractiveTUIApp.reload_env_file()` mutates this
        # same object in place to propagate a live env-file reload here.
        self.default_map = {} if default_map is None else default_map
        self.unrecognized = [] if unrecognized is None else unrecognized

    def compose(self) -> ComposeResult:
        yield Header()
        yield Logo()
        yield OptionList(
            *[
                Option(_menu_option_prompt(name, self.commands[name]), id=name)
                for name in sorted(self.commands)
            ]
        )
        if self.unrecognized:
            yield Static(self._warning_text(), id="unrecognized-keys-warning")
        yield Footer()

    def _warning_text(self) -> str:
        return f"Warning: unrecognized key(s) in env file: {', '.join(self.unrecognized)}"

    async def refresh_unrecognized_warning(self) -> None:
        """Re-render the below-menu warning row from the current (possibly
        just-reloaded) ``self.unrecognized`` -- called after the config
        editor writes to the same env-file this session is using. Async:
        mounting/removing a widget (as opposed to always keeping it mounted
        and toggling `.display`, which would break the "absent when there's
        nothing to warn about, not present-but-empty" contract) must be
        awaited for the DOM change to actually take effect."""
        existing = self.query("#unrecognized-keys-warning")
        if self.unrecognized:
            if existing:
                existing.first(Static).update(self._warning_text())
            else:
                await self.mount(
                    Static(self._warning_text(), id="unrecognized-keys-warning"),
                    before=self.query_one(Footer),
                )
        elif existing:
            await existing.first().remove()

    def on_resize(self, event: events.Resize) -> None:
        self.query_one(Logo).set_visible_for_size(*event.size)

    async def on_screen_resume(self) -> None:
        """Every time this screen becomes active again (initial display, or
        returning from any other screen), re-read the active `--env-file`.
        Covers not just a save from this session's own config editor, but any
        external edit made while a different screen was on top (e.g. `config
        set` run in another terminal, or the file edited outside the TUI)."""
        reload_env_file = getattr(self.app, "reload_env_file", None)
        if reload_env_file is not None:
            await reload_env_file()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        name = str(event.option.id)
        command = self.commands[name]
        screen_cls = _SPECIALIZED_SCREENS.get(name)
        if screen_cls is MigrateScreen:
            # migrate's target_version/chunks_per_shard are registry-configurable
            # (shared with from_images) -- pre-fill them from the env-file too.
            self.app.push_screen(MigrateScreen(command, self.default_map.get(name)))
        elif screen_cls is not None:
            self.app.push_screen(screen_cls(command))
        else:
            self.app.push_screen(CommandFormScreen(command, self.default_map.get(name)))

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

    def __init__(self, command: click.Command, default_map: dict[str, str] | None = None) -> None:
        super().__init__()
        self.command = command
        self._default_map = default_map or {}
        self._field_specs: list[FieldSpec] = []
        self._required_frame: Vertical | None = None
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._pending_result: GenericResultScreen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            self._field_specs = [
                build_field_spec(param, self._default_map.get(param.name))
                for param in self.command.params
            ]
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
            default_map=self._default_map,
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
        await self.app.switch_screen(CommandFormScreen(self.command, self._default_map))

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

    def __init__(
        self,
        commands: dict[str, click.Command],
        default_map: dict[str, dict[str, str]] | None = None,
        unrecognized: list[str] | None = None,
        env_file: str | None = None,
    ) -> None:
        super().__init__()
        self.commands = commands
        # `is None` (not `or`): keeps these the *same* dict/list objects
        # `reload_env_file()` mutates in place, and that `CommandMenuScreen`
        # (constructed from them below) ends up sharing identity with --
        # reassigning to a brand-new empty container here would silently
        # decouple the two the moment either started out empty.
        self.default_map = {} if default_map is None else default_map
        self.unrecognized = [] if unrecognized is None else unrecognized
        self.env_file = env_file

    def on_mount(self) -> None:
        self.push_screen(CommandMenuScreen(self.commands, self.default_map, self.unrecognized))

    async def reload_env_file(self) -> None:
        """Re-read ``self.env_file`` from disk and refresh the cached
        ``default_map``/``unrecognized`` used to pre-fill fields and the
        menu's warning row -- called after the config editor writes to this
        same file, so a change made mid-session is reflected immediately
        instead of only after restarting the whole ``--tui`` session."""
        if not self.env_file:
            return

        from pathlib import Path

        from ome_zarr_tools.core.config_registry import build_default_map, unrecognized_keys
        from ome_zarr_tools.core.env_file import read_env_file
        from ome_zarr_tools.core.errors import CliError

        try:
            values, _dup_warnings = read_env_file(Path(self.env_file))
        except CliError:
            values = {}

        self.default_map.clear()
        self.default_map.update(build_default_map(values))
        self.unrecognized[:] = unrecognized_keys(values)

        for screen in self.screen_stack:
            if isinstance(screen, CommandMenuScreen):
                await screen.refresh_unrecognized_warning()
                break
