"""`inspect` screen: prep screen (ZARR_PATH field) + its own Result screen (spec 004 US7).

Read-only (`inspect` never writes). The summary/JSON report is only ever
known once the command actually runs, so -- unlike `fix_metadata`/`migrate`'s
always-shown live preview -- it now lives entirely on `InspectResultScreen`,
built the moment Run finishes; the prep screen holds nothing but the field.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, TextArea

from ome_zarr_tools.commands.inspect import build_report, format_text
from ome_zarr_tools.core.zarr_path import is_remote_path
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


class InspectResultScreen(CommandResultScreen):
    def __init__(self, command: click.Command, report: dict | None = None) -> None:
        super().__init__(command)
        self.report: dict | None = report

    def compose_result_content(self) -> ComposeResult:
        if self.report is None:
            return
        yield TextArea(format_text(self.report), read_only=True, id="summary-view")
        for level in self.report["levels"]:
            yield TextArea(
                json.dumps(level, indent=2),
                language="json",
                read_only=True,
                id=f"json-level-{level['path']}",
            )


class InspectScreen(Screen[None]):
    BINDINGS = [*shared_bindings(), Binding("f4", "restore_defaults", "Restore Defaults")]

    DEFAULT_CSS = """
    #bottom-bar {
        dock: bottom;
        height: auto;
    }
    """

    def __init__(self, command: click.Command) -> None:
        super().__init__()
        self.command = command
        self._field_specs: list[FieldSpec] = []
        self._required_frame: Vertical | None = None
        self._path_field: PathField | None = None
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._pending_result: InspectResultScreen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            zarr_path_param = next(p for p in self.command.params if p.name == "zarr_path")
            spec = build_field_spec(zarr_path_param)
            assert isinstance(spec.widget, PathField)
            self._path_field = spec.widget
            self._field_specs = [spec]
            for frame in build_field_frames(self._field_specs):
                if frame.id == "required-frame":
                    self._required_frame = frame
                yield frame
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._required_frame is not None:
            refresh_required_subtitle(self._required_frame, self._field_specs)

    def _invocation_text(self) -> str:
        assert self._path_field is not None
        return f"ome-zarr-tools inspect {self._path_field.value}".strip()

    def _path_is_usable(self, path_str: str) -> bool:
        return bool(path_str) and (is_remote_path(path_str) or Path(path_str).exists())

    def action_run(self) -> None:
        assert self._path_field is not None
        path_str = self._path_field.value.strip()
        if not self._path_is_usable(path_str):
            self._path_field.input.focus()
            self.notify("ZARR_PATH is required", severity="error")
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        result_holder: dict[str, dict] = {}

        def _work() -> None:
            report = build_report(path_str)
            result_holder["report"] = report
            click.echo(format_text(report))  # same text a direct `inspect` CLI run would print

        self._path_field.disabled = True
        result_screen = InspectResultScreen(self.command)
        self._pending_result = result_screen
        self.app.push_screen(result_screen)
        on_progress, on_log = result_screen.begin()

        async def _on_done(result: ExecutionResult) -> None:
            self._pending_result = None
            assert self._path_field is not None
            self._path_field.disabled = False
            result_screen.report = result_holder.get("report")
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
        await self.app.switch_screen(InspectScreen(self.command))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.exit(result=None)
