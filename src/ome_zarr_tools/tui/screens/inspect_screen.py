"""`inspect` screen: JSON-per-level panel + summary panel, switchable (FR-016).

Read-only (`inspect` never writes). Both panels are sourced from
``commands/inspect.py``'s existing ``build_report``/``format_text`` -- reused,
not reimplemented, per data-model.md's Inspect Panels section. Nothing is
built until Run (F5) is pressed -- unlike `fix_metadata`/`migrate`'s
always-shown live preview (FR-018 is specific to those two), inspecting a
remote (`gs://`/`s3://`) dataset means a network round-trip, so building on
every keystroke would fire one per character typed.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, TextArea

from ome_zarr_tools.commands.inspect import build_report, format_text
from ome_zarr_tools.core.zarr_path import is_remote_path
from ome_zarr_tools.tui.execution import ExecutionResult, run_in_background
from ome_zarr_tools.tui.fields import SafePathAutoComplete
from ome_zarr_tools.tui.status import StatusPanel


class InspectScreen(Screen[None]):
    BINDINGS = [
        Binding("f5", "run", "Run"),
        Binding("f6", "copy", "Copy"),
        Binding("f7", "copy_and_exit", "Copy & exit"),
        Binding("f8", "toggle_log", "Log"),
        Binding("f9", "switch_panel", "Switch panel"),
        Binding("escape", "back", "Back to menu"),
        Binding("ctrl+c", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    #bottom-bar {
        dock: bottom;
        height: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._path_input = Input(placeholder="ZARR_PATH", id="field-zarr_path")
        self._summary_label = Label("Summary", id="summary-label")
        self._summary_view = TextArea("", read_only=True, id="summary-view")
        self._json_container = Vertical(id="json-panels")
        self._active_panel = "summary"  # "summary" | "json"
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._report: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("ZARR_PATH *")
            yield self._path_input
            yield SafePathAutoComplete(self._path_input, path=".")
            yield self._summary_label
            yield self._summary_view
            yield self._json_container
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_mount(self) -> None:
        self._refresh_panel_visibility()

    async def _rebuild_json_panels(self) -> None:
        assert self._report is not None
        await self._json_container.remove_children()
        for level in self._report["levels"]:
            await self._json_container.mount(Label(f"Level {level['path']}"))
            await self._json_container.mount(
                TextArea(
                    json.dumps(level, indent=2),
                    language="json",
                    read_only=True,
                    id=f"json-level-{level['path']}",
                )
            )

    def action_switch_panel(self) -> None:
        self._active_panel = "json" if self._active_panel == "summary" else "summary"
        self._refresh_panel_visibility()

    def _refresh_panel_visibility(self) -> None:
        show_summary = self._active_panel == "summary"
        self._summary_label.display = show_summary
        self._summary_view.display = show_summary
        self._json_container.display = not show_summary

    def _invocation_text(self) -> str:
        return f"ome-zarr-tools inspect {self._path_input.value}".strip()

    def _path_is_usable(self, path_str: str) -> bool:
        return bool(path_str) and (is_remote_path(path_str) or Path(path_str).exists())

    def action_run(self) -> None:
        path_str = self._path_input.value.strip()
        if not self._path_is_usable(path_str):
            self._path_input.focus()
            self.notify("ZARR_PATH is required", severity="error")
            return

        result_holder: dict[str, dict] = {}

        def _work() -> None:
            report = build_report(path_str)
            result_holder["report"] = report
            click.echo(format_text(report))  # same text a direct `inspect` CLI run would print

        self._status_panel.start()
        run_in_background(
            self.app,
            _work,
            lambda result: self._on_execution_done(result, result_holder.get("report")),
            on_progress=self._status_panel.update_progress,
            on_log=self._status_panel.append_log,
        )

    async def _on_execution_done(self, result: ExecutionResult, report: dict | None) -> None:
        self._status_panel.stop()
        if result.succeeded:
            self._report = report
            if self._report is not None:
                self._summary_view.text = format_text(self._report)
                await self._rebuild_json_panels()
            self._log_lines.append("inspect succeeded.")
            self.notify("inspect succeeded.")
        else:
            self._log_lines.append(f"inspect failed: {result.error}")
            self.notify(f"inspect failed: {result.error}", severity="error")

    def action_copy(self) -> None:
        invocation = self._invocation_text()
        self.app.copy_to_clipboard(invocation)
        self._log_lines.append(f"Copied: {invocation}")
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
