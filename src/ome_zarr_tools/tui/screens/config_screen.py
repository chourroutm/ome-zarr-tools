"""`config` screen: scope picker, current-vs-defaults view, editable JSON (FR-017),
plus its own Result screen showing the written config JSON (spec 004 US7).

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
from pathlib import Path

import click
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, Select, TextArea

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
        self._current_view = TextArea("", language="json", read_only=True, id="current-view")
        self._defaults_view = TextArea(
            json.dumps(collect_default_values(), indent=2),
            language="json",
            read_only=True,
            id="defaults-view",
        )
        self._editor = TextArea("{}", language="json", id="editor")
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._pending_result: ConfigResultScreen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            field_specs = [
                FieldSpec(label="Scope", widget=self._scope_select, required=False),
                FieldSpec(
                    label="",
                    widget=Vertical(self._project_dir_label, self._project_dir_input),
                    required=False,
                ),
            ]
            yield from build_field_frames(field_specs)
            yield Label("Current preferences (this scope)")
            yield self._current_view
            yield Label("Built-in defaults (for comparison)")
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
        text = json.dumps(cfg, indent=2) if cfg else "{}"
        self._current_view.text = text
        self._editor.text = text

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
            if result.succeeded:
                self._current_view.text = self._editor.text
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
        self.app.exit(result=None)

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
