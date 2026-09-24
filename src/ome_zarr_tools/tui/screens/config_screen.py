"""`config` screen: an ENV_FILE path field, a plain-text KEY=VALUE editor,
a click-to-insert view of the registry's configurable variables and their
defaults, plus its own Result screen showing the written file's content
(spec 004 US7, rewritten for 009-config-env-vars's env-file format).

Reuses ``core/env_file.py``'s ``read_env_file``/``write_env_file``/
``parse_env_text`` (data-model.md § Config Editor) rather than reimplementing
file I/O or parsing here. Save parses the edited text and rejects any
unrecognized ``OME_ZARR_TOOLS_*`` key (blocking, edit preserved) before
writing -- the TUI equivalent of running `config set`, so it uses that
context's error-level severity (FR-016).
"""

from __future__ import annotations

import re
from pathlib import Path

import click
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, TextArea

from ome_zarr_tools.core.config_registry import CONFIGURABLE_VARIABLES, unrecognized_keys
from ome_zarr_tools.core.env_file import parse_env_text, read_env_file, write_env_file
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.tui.execution import ExecutionResult, run_in_background
from ome_zarr_tools.tui.fields import (
    FieldSpec,
    PathField,
    build_field_frames,
    build_field_spec,
    build_identity_frame,
    refresh_required_subtitle,
)
from ome_zarr_tools.tui.screens.result_screen import CommandResultScreen
from ome_zarr_tools.tui.shortcuts import shared_bindings
from ome_zarr_tools.tui.status import StatusPanel


class DefaultEntryButton(Button):
    """One registry-known configurable variable's default, rendered as a
    compact, left-aligned button styled like the ``KEY=VALUE`` line it would
    insert. Pressing it inserts that line into the editor; if the key is
    already present, the cursor moves to the start of its existing value
    instead (left untouched)."""

    default_key: str

    DEFAULT_CSS = """
    DefaultEntryButton {
        width: 100%;
        content-align: left middle;
        text-align: left;
        background: $surface !important;
        background-tint: 0% !important;
        border: none !important;

        &:hover {
            background: $surface-darken-1 !important;
        }
    }
    """

    def __init__(self, key: str, value: object) -> None:
        display_value = "" if value is None else value
        label = f"[cyan]{key}[/]=[green]{display_value}[/]"
        super().__init__(label, compact=True, classes="default-entry")
        self.default_key = key


def build_defaults_entries() -> list[DefaultEntryButton]:
    """One button per registry-known configurable variable -- all 13, not just
    the ones whose target option happens to have a non-``None`` built-in
    default (e.g. ``--chunks_per_shard``/``--smooth`` default to ``None``,
    meaning "omit the flag"; they're still legitimate configurable variables
    and must still get a button, just with a blank value to fill in). Sourced
    directly from each variable's first target option's real
    ``click.Option.default`` -- not a second, independently maintained list
    (this is the fix for the pre-existing `output_format` name collision the
    old ``collect_default_values()`` had, applied to the TUI's reference view
    too)."""
    from ome_zarr_tools.cli import cli

    params_by_command = {
        name: {p.name: p for p in cmd.params} for name, cmd in cli.commands.items()
    }

    entries: list[DefaultEntryButton] = []
    for variable in CONFIGURABLE_VARIABLES:
        command_name, option_name = variable.targets[0]
        param = params_by_command[command_name][option_name]
        entries.append(DefaultEntryButton(variable.name, param.default))
    return entries


def _locate_existing_key(text: str, key: str) -> int | None:
    """Return the offset right after ``KEY=`` on its own line -- i.e. the
    start of its value -- or None if that key isn't present."""
    match = re.search(rf"^{re.escape(key)}=", text, re.MULTILINE)
    return None if match is None else match.end()


def _location_from_offset(text: str, offset: int) -> tuple[int, int]:
    """Convert a plain codepoint offset into ``text`` to a ``(row, column)``
    location, as ``TextArea`` addresses positions."""
    prefix = text[:offset]
    row = prefix.count("\n")
    column = offset - (prefix.rfind("\n") + 1)
    return row, column


class ConfigResultScreen(CommandResultScreen):
    def __init__(self, command: click.Command, env_text: str) -> None:
        super().__init__(command)
        self.env_text = env_text

    def compose_result_content(self) -> ComposeResult:
        yield TextArea(self.env_text, read_only=True)


class ConfigScreen(Screen[None]):
    BINDINGS = [
        *shared_bindings(primary_label="Save"),
        Binding("f4", "restore_defaults", "Restore Defaults"),
    ]

    DEFAULT_CSS = """
    #bottom-bar {
        dock: bottom;
        height: auto;
    }
    #defaults-view {
        border: tall $border-blurred;
        padding: 0 1;
        background: $surface;
        color: $foreground;
    }
    """

    def __init__(self, command: click.Command) -> None:
        super().__init__()
        self.command = command
        assert isinstance(command, click.Group)
        env_file_param = next(p for p in command.commands["set"].params if p.name == "env_file")
        spec = build_field_spec(env_file_param)
        assert isinstance(spec.widget, PathField)
        self._path_field = spec.widget
        self._field_specs: list[FieldSpec] = [spec]
        self._required_frame: Vertical | None = None
        self._defaults_view = Vertical(*build_defaults_entries(), id="defaults-view")
        self._defaults_view.styles.height = "auto"
        self._editor = TextArea("", id="editor")
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._pending_result: ConfigResultScreen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            for frame in build_field_frames(self._field_specs):
                if frame.id == "required-frame":
                    self._required_frame = frame
                yield frame
            yield Label("Configurable variables (click to insert into the editor below)")
            yield self._defaults_view
            yield Label("Editable ENV_FILE content")
            yield self._editor
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_mount(self) -> None:
        self._load_current()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._required_frame is not None:
            refresh_required_subtitle(self._required_frame, self._field_specs)
        self._load_current()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, DefaultEntryButton):
            self._insert_default_key(event.button)

    def _insert_default_key(self, button: DefaultEntryButton) -> None:
        key = button.default_key
        # `str(button.label)` would include the Rich markup; re-derive the
        # plain value from the registry instead of parsing the label back.
        from ome_zarr_tools.cli import cli

        params_by_command = {
            name: {p.name: p for p in cmd.params} for name, cmd in cli.commands.items()
        }
        variable = next(v for v in CONFIGURABLE_VARIABLES if v.name == key)
        command_name, option_name = variable.targets[0]
        default = params_by_command[command_name][option_name].default
        value = "" if default is None else default

        text = self._editor.text
        value_start = _locate_existing_key(text, key)
        if value_start is not None:
            self._editor.cursor_location = _location_from_offset(text, value_start)
        else:
            prefix = "" if not text or text.endswith("\n") else "\n"
            snippet = f"{prefix}{key}={value}"
            location = _location_from_offset(text, len(text))
            result = self._editor.insert(snippet, location, maintain_selection_offset=False)
            self._editor.cursor_location = result.end_location
        self._editor.focus()

    def _load_current(self) -> None:
        path_str = self._path_field.value.strip()
        if not path_str or not Path(path_str).is_file():
            self._editor.text = ""
            return
        try:
            values, _dup_warnings = read_env_file(Path(path_str))
        except CliError:
            self._editor.text = ""
            return
        self._editor.text = "".join(f"{k}={v}\n" for k, v in values.items())

    def _invocation_text(self) -> str:
        return f"ome-zarr-tools config set {self._path_field.value} <KEY=VALUE ...>".strip()

    def action_run(self) -> None:
        path_str = self._path_field.value.strip()
        if not path_str:
            self._path_field.input.focus()
            self.notify("ENV_FILE is required", severity="error")
            return

        try:
            values, _dup_warnings = parse_env_text(self._editor.text, source=path_str)
        except CliError as exc:
            self.notify(str(exc), severity="error")
            return

        unrecognized = unrecognized_keys(values)
        if unrecognized:
            self.notify(f"Unrecognized key(s): {', '.join(unrecognized)}", severity="error")
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        path = Path(path_str)
        env_text = "".join(f"{k}={v}\n" for k, v in values.items())

        def _work() -> None:
            write_env_file(path, values)

        result_screen = ConfigResultScreen(self.command, env_text)
        self._pending_result = result_screen
        self.app.push_screen(result_screen)
        on_progress, on_log = result_screen.begin()

        async def _on_done(result: ExecutionResult) -> None:
            self._pending_result = None
            await result_screen.finish(result)

        run_in_background(
            self.app,
            _work,
            _on_done,
            on_progress=on_progress,
            on_log=on_log,
        )

    def action_copy(self) -> None:
        invocation = self._invocation_text()
        self.app.copy_to_clipboard(invocation)
        self._log_lines.append(f"Copied: {invocation}")
        self._status_panel.append_log(f"Copied: {invocation}")
        self.notify("Copied to clipboard (and logged).")

    def action_copy_and_exit(self) -> None:
        self.action_copy()
        self.app.exit(result=self._invocation_text())

    def action_toggle_log(self) -> None:
        self._status_panel.toggle_log()

    async def action_restore_defaults(self) -> None:
        if self._pending_result is not None:
            return
        await self.app.switch_screen(ConfigScreen(self.command))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.exit(result=None)
