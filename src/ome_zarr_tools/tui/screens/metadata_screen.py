"""``fix_metadata``/``migrate`` screens: always-shown diff + rich view (FR-018/FR-019).

Neither screen invokes its command via ``command.main()`` -- both commands have
an internal ``click.confirm``/``click.prompt`` gate that would hang on stdin
from a worker thread (research.md). Instead, Run calls each command's
extracted, non-interactive write function directly (``write_metadata``,
``apply_migration``), via the same worker-thread mechanism every other
command uses (``tui/execution.py``'s ``run_in_background``).
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import zarr
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, RichLog, TextArea

from ome_zarr_tools.commands.fix_metadata import build_proposed_multiscales, write_metadata
from ome_zarr_tools.commands.migrate import (
    DEFAULT_TARGET_VERSION,
    apply_migration,
    preview_migration,
)
from ome_zarr_tools.io.ome_metadata import detect_version, read_multiscales
from ome_zarr_tools.tui.diff import render_diff
from ome_zarr_tools.tui.execution import ExecutionResult, run_in_background
from ome_zarr_tools.tui.fields import SafePathAutoComplete
from ome_zarr_tools.tui.status import StatusPanel


class _BaseMetadataScreen(Screen[None]):
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

    def __init__(self) -> None:
        super().__init__()
        self._log_lines: list[str] = []
        self._error: str | None = None
        self._status_panel = StatusPanel()

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)

    def _invocation_text(self) -> str:
        raise NotImplementedError

    def action_toggle_log(self) -> None:
        self._status_panel.toggle_log()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.exit(result=None)

    def action_copy(self) -> None:
        invocation = self._invocation_text()
        self.app.copy_to_clipboard(invocation)
        self._append_log(f"Copied: {invocation}")
        self.notify("Copied to clipboard (and logged).")

    def action_copy_and_exit(self) -> None:
        self.action_copy()
        self.app.exit(result=None)

    def _on_execution_done(self, result: ExecutionResult, label: str) -> None:
        self._status_panel.stop()
        if result.succeeded:
            self._append_log(f"{label} succeeded.")
            self.notify(f"{label} succeeded.")
        else:
            self._append_log(f"{label} failed: {result.error}")
            self.notify(f"{label} failed: {result.error}", severity="error")


class FixMetadataScreen(_BaseMetadataScreen):
    def __init__(self) -> None:
        super().__init__()
        self._path_input = Input(placeholder="ZARR_PATH", id="field-zarr_path")
        self._diff_log = RichLog(id="diff", auto_scroll=False)
        self._rich_view = TextArea(language="json", id="rich-view")
        self._before: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("ZARR_PATH *")
            yield self._path_input
            yield SafePathAutoComplete(self._path_input, path=".")
            yield Label("Diff (current vs. proposed)")
            yield self._diff_log
            yield Label("Proposed metadata (editable)")
            yield self._rich_view
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._load_and_preview()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._refresh_diff()

    def _load_and_preview(self) -> None:
        path_str = self._path_input.value.strip()
        if not path_str or not Path(path_str).exists():
            return
        try:
            group = zarr.open_group(path_str, mode="r")
        except Exception:
            return

        multiscales = read_multiscales(group)
        self._before = multiscales[0] if multiscales else None

        default_name = multiscales[0].get("name") if multiscales else None
        name = default_name or "Image"

        default_unit = None
        if multiscales and multiscales[0].get("axes"):
            default_unit = multiscales[0]["axes"][0].get("unit")
        spatial_unit = default_unit or "micrometer"

        default_voxel: tuple[float, ...] | None = None
        if multiscales:
            datasets = multiscales[0].get("datasets", [])
            if datasets:
                for transform in datasets[0].get("coordinateTransformations", []):
                    if transform.get("type") == "scale":
                        default_voxel = tuple(float(x) for x in transform["scale"])
                        break
        voxel_size = default_voxel or (1.0, 1.0, 1.0)

        default_axes = ["z", "y", "x"]
        if multiscales and multiscales[0].get("axes"):
            default_axes = [
                axis.get("name", d)
                for axis, d in zip(multiscales[0]["axes"], default_axes, strict=False)
            ]

        dataset_paths = [d["path"] for d in multiscales[0]["datasets"]] if multiscales else ["0"]

        proposed = build_proposed_multiscales(
            name, spatial_unit, voxel_size, default_axes, dataset_paths
        )
        self._rich_view.text = json.dumps(proposed, indent=2)
        self._refresh_diff()

    def _current_proposed(self) -> list[dict] | None:
        try:
            parsed = json.loads(self._rich_view.text)
        except json.JSONDecodeError as exc:
            self._error = f"Invalid JSON: {exc}"
            return None
        self._error = None
        return parsed

    def _refresh_diff(self) -> None:
        proposed = self._current_proposed()
        after = proposed[0] if proposed else {}
        render_diff(self._diff_log, self._before, after)

    def _invocation_text(self) -> str:
        return f"ome-zarr-tools fix_metadata {self._path_input.value}".strip()

    def action_run(self) -> None:
        path_str = self._path_input.value.strip()
        if not path_str or not Path(path_str).exists():
            self._path_input.focus()
            self.notify("ZARR_PATH is required", severity="error")
            return
        proposed = self._current_proposed()
        if proposed is None:
            self.notify(self._error or "Invalid metadata", severity="error")
            return

        path = Path(path_str)
        group = zarr.open_group(path_str, mode="r+")
        self._path_input.disabled = True
        self._rich_view.disabled = True

        def _work() -> None:
            write_metadata(path, group, proposed)

        self._status_panel.start()
        run_in_background(
            self.app,
            _work,
            lambda r: self._on_execution_done(r, "fix_metadata"),
            on_progress=self._status_panel.update_progress,
            on_log=self._status_panel.append_log,
        )


class MigrateScreen(_BaseMetadataScreen):
    def __init__(self) -> None:
        super().__init__()
        self._path_input = Input(placeholder="ZARR_PATH", id="field-zarr_path")
        self._target_input = Input(value=DEFAULT_TARGET_VERSION, id="field-target_version")
        self._diff_log = RichLog(id="diff", auto_scroll=False)
        self._rich_view = TextArea(language="json", id="rich-view", read_only=True)
        self._before: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("ZARR_PATH *")
            yield self._path_input
            yield SafePathAutoComplete(self._path_input, path=".")
            yield Label("--target_version")
            yield self._target_input
            yield Label("Diff (current vs. migrated)")
            yield self._diff_log
            yield Label("Preview of migrated metadata (read-only)")
            yield self._rich_view
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._load_and_preview()

    def _load_and_preview(self) -> None:
        path_str = self._path_input.value.strip()
        target_version = self._target_input.value.strip() or DEFAULT_TARGET_VERSION
        if not path_str or not Path(path_str).exists():
            return
        path = Path(path_str)
        try:
            group = zarr.open_group(path_str, mode="r")
        except Exception:
            return

        self._before = dict(group.attrs)
        try:
            after = preview_migration(path, target_version)
            self._error = None
        except click.ClickException as exc:
            self._error = str(exc)
            after = {}
        except Exception as exc:
            self._error = str(exc)
            after = {}

        self._rich_view.text = json.dumps(after, indent=2)
        render_diff(self._diff_log, self._before, after)

    def _invocation_text(self) -> str:
        return (
            f"ome-zarr-tools migrate {self._path_input.value} "
            f"--target_version {self._target_input.value}"
        ).strip()

    def action_run(self) -> None:
        path_str = self._path_input.value.strip()
        if not path_str or not Path(path_str).exists():
            self._path_input.focus()
            self.notify("ZARR_PATH is required", severity="error")
            return
        if self._error:
            self.notify(self._error, severity="error")
            return

        target_version = self._target_input.value.strip() or DEFAULT_TARGET_VERSION
        path = Path(path_str)
        source_version = detect_version(zarr.open_group(path_str, mode="r"))
        if source_version == target_version:
            self._append_log(f"{path_str} is already at version {target_version}; nothing to do.")
            self.notify("Already at target version; nothing to do.")
            return

        group = zarr.open_group(path_str, mode="r")
        self._path_input.disabled = True
        self._target_input.disabled = True

        def _work() -> None:
            apply_migration(path, group, target_version)

        self._status_panel.start()
        run_in_background(
            self.app,
            _work,
            lambda r: self._on_execution_done(r, "migrate"),
            on_progress=self._status_panel.update_progress,
            on_log=self._status_panel.append_log,
        )
