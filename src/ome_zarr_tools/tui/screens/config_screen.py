"""`config` screen: scope picker, a click-to-insert view of the built-in
defaults, editable JSON (FR-017), plus its own Result screen showing the
written config JSON (spec 004 US7).

Reuses ``commands/config.py``'s existing ``read_config``/``write_config``/
``target_config_path`` (data-model.md § Config Editor) rather than reformatting
config-file logic here. Save validates JSON syntax (blocking, edit preserved,
per the Edge Cases table) then writes the whole parsed object directly --
`config set`'s key=value CLI form can't losslessly round-trip nested JSON, so
this bypasses ``config.main()`` the same way `fix_metadata`/`migrate` bypass
their commands for their own extracted write functions (research.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import click
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, TextArea

from ome_zarr_tools.commands.config import read_config, target_config_path, write_config
from ome_zarr_tools.tui.execution import ExecutionResult, run_in_background
from ome_zarr_tools.tui.fields import FieldSpec, build_field_frames, build_identity_frame
from ome_zarr_tools.tui.screens.result_screen import CommandResultScreen
from ome_zarr_tools.tui.shortcuts import shared_bindings
from ome_zarr_tools.tui.status import StatusPanel


def collect_default_values() -> dict[str, object]:
    """The tool's built-in option defaults, gathered for comparison (not a config-file tier)."""
    from ome_zarr_tools.cli import cli

    defaults: dict[str, object] = {}
    for name, command in cli.commands.items():
        if name in ("config", "interactive"):
            continue
        for param in command.params:
            if not isinstance(param, click.Option) or param.required or param.default is None:
                continue
            try:
                json.dumps(param.default)
            except TypeError:
                continue  # e.g. click's internal sentinel for unresolved multi-value defaults
            defaults.setdefault(param.name, param.default)
    return defaults


class DefaultEntryButton(Button):
    """One built-in default, rendered as a compact, left-aligned, full-width
    button styled to look like the JSON line it would become -- same 2-space
    indent and trailing comma as the editor below, a flat uniform background
    (only ``:hover`` stands out, to signal it's clickable without looking like
    a row of pills). Pressing it inserts ``"key": `` as its own new line in
    the config editor (adding a comma to the previous entry if needed),
    cursor landing right after the colon. If that key is already present,
    the cursor is placed at the start of its existing value instead, which is
    left untouched."""

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

    def __init__(self, key: str, value: object, *, trailing_comma: bool = True) -> None:
        comma = "," if trailing_comma else ""
        label = f'  [cyan]"{key}"[/]: [green]{json.dumps(value)}[/]{comma}'
        super().__init__(label, compact=True, classes="default-entry")
        self.default_key = key


def build_defaults_entries(defaults: dict[str, object]) -> list[Label | DefaultEntryButton]:
    """The full click-to-insert defaults block, styled like a real JSON object:
    an unindented ``{``, one left-aligned button per default (comma-separated,
    the last one bare), and an unindented ``}``."""
    keys = list(defaults)
    entries: list[Label | DefaultEntryButton] = [Label("{")]
    for index, key in enumerate(keys):
        entries.append(DefaultEntryButton(key, defaults[key], trailing_comma=index < len(keys) - 1))
    entries.append(Label("}"))
    return entries


def _locate_existing_key(text: str, key: str) -> int | None:
    """Return the offset right after ``"key":`` (and any following whitespace)
    for ``"key": <value>`` in ``text`` -- i.e. the start of its value -- or
    None if that key isn't present."""
    match = re.search(rf'"{re.escape(key)}"\s*:\s*', text)
    return None if match is None else match.end()


def _location_from_offset(text: str, offset: int) -> tuple[int, int]:
    """Convert a plain codepoint offset into ``text`` to a ``(row, column)``
    location, as ``TextArea`` addresses positions. Hand-rolled rather than
    ``TextArea.document.get_location_from_index`` because the latter is typed
    against the abstract ``DocumentBase``, which doesn't guarantee it."""
    prefix = text[:offset]
    row = prefix.count("\n")
    column = offset - (prefix.rfind("\n") + 1)
    return row, column


def _new_key_insertion(text: str, key: str) -> tuple[int, str, int | None]:
    """Return ``(offset, text_to_insert, newline_fix_offset)`` for adding
    ``"key": `` as its own new line inside the top-level JSON object, just
    before its closing brace -- with a leading comma if the object already
    has other entries. ``newline_fix_offset``, when not None, is a position
    (in the original ``text``) where a bare "\\n" must be inserted *first* --
    there wasn't already one separating the last entry from the closing
    brace (e.g. a compact ``{}``), so without it the new entry would end up
    sharing a line with that brace."""
    close_index = text.rfind("}")
    if close_index == -1:
        return len(text), f'"{key}": ', None
    body = text[:close_index].rstrip()
    trailing_whitespace = text[len(body) : close_index]
    prefix = "" if body.endswith("{") else ","
    newline_fix_offset = None if "\n" in trailing_whitespace else close_index
    return len(body), f'{prefix}\n  "{key}": ', newline_fix_offset


class ConfigResultScreen(CommandResultScreen):
    def __init__(self, command: click.Command, config_json: str) -> None:
        super().__init__(command)
        self.config_json = config_json

    def compose_result_content(self) -> ComposeResult:
        yield TextArea(self.config_json, language="json", read_only=True)


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
        self._scope_select: Select[str] = Select(
            [("user", "user"), ("project", "project")],
            value="user",
            allow_blank=False,
            id="field-scope",
        )
        self._project_dir_label = Label("Project directory")
        self._project_dir_input = Input(placeholder=str(Path.cwd()), id="field-project_dir")
        self._defaults_view = Vertical(
            *build_defaults_entries(collect_default_values()),
            id="defaults-view",
        )
        self._defaults_view.styles.height = "auto"
        self._editor = TextArea("{}", language="json", id="editor")
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._pending_result: ConfigResultScreen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            project_dir_group = Vertical(self._project_dir_label, self._project_dir_input)
            project_dir_group.styles.height = "auto"
            field_specs = [
                FieldSpec(label="Scope", widget=self._scope_select, required=False),
                FieldSpec(label="", widget=project_dir_group, required=False),
            ]
            yield from build_field_frames(field_specs)
            yield Label("Built-in defaults (click to insert into the JSON below)")
            yield self._defaults_view
            yield Label("Editable config JSON")
            yield self._editor
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_mount(self) -> None:
        self._refresh_scope_visibility()
        self._load_current()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh_scope_visibility()
        self._load_current()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._load_current()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, DefaultEntryButton):
            self._insert_default_key(event.button.default_key)

    def _insert_default_key(self, key: str) -> None:
        text = self._editor.text
        colon_end = _locate_existing_key(text, key)
        if colon_end is not None:
            self._editor.cursor_location = _location_from_offset(text, colon_end)
        else:
            offset, snippet, newline_fix_offset = _new_key_insertion(text, key)
            if newline_fix_offset is not None:
                fix_location = _location_from_offset(text, newline_fix_offset)
                self._editor.insert("\n", fix_location, maintain_selection_offset=False)
            location = _location_from_offset(text, offset)
            result = self._editor.insert(snippet, location, maintain_selection_offset=False)
            self._editor.cursor_location = result.end_location
        self._editor.focus()

    def _refresh_scope_visibility(self) -> None:
        is_project = self._scope_select.value == "project"
        self._project_dir_label.display = is_project
        self._project_dir_input.display = is_project

    def _target_path(self) -> Path:
        if self._scope_select.value == "user":
            return target_config_path(True, None)
        project_dir = self._project_dir_input.value.strip() or str(Path.cwd())
        return target_config_path(False, project_dir)

    def _load_current(self) -> None:
        cfg = read_config(self._target_path())
        self._editor.text = json.dumps(cfg, indent=2) if cfg else "{}"

    def _invocation_text(self) -> str:
        if self._scope_select.value == "user":
            return "ome-zarr-tools config set --user <key=value ...>"
        project_dir = self._project_dir_input.value.strip() or str(Path.cwd())
        return f"ome-zarr-tools config set --project {project_dir} <key=value ...>"

    def action_run(self) -> None:
        try:
            parsed = json.loads(self._editor.text)
        except json.JSONDecodeError as exc:
            self.notify(f"Invalid JSON: {exc}", severity="error")
            return
        if not isinstance(parsed, dict):
            self.notify("Config must be a JSON object.", severity="error")
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        path = self._target_path()
        config_json = json.dumps(parsed, indent=2)

        def _work() -> None:
            write_config(path, parsed)

        result_screen = ConfigResultScreen(self.command, config_json)
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
