"""``fix_metadata``/``migrate`` screens: always-shown diff + rich view (FR-018/FR-019),
plus their own Result screens showing the diff that was actually applied (spec 004 US7).

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
from rich.console import Group
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, RichLog, Static, TextArea

from ome_zarr_tools.commands.fix_metadata import build_proposed_multiscales, write_metadata
from ome_zarr_tools.commands.migrate import (
    DEFAULT_TARGET_VERSION,
    apply_migration,
    preview_migration,
)
from ome_zarr_tools.io.ome_metadata import detect_version, read_multiscales
from ome_zarr_tools.tui.diff import diff_lines, render_diff
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


class FixMetadataResultScreen(CommandResultScreen):
    def __init__(self, command: click.Command, before: dict | None, after: dict) -> None:
        super().__init__(command)
        self.before = before
        self.after = after

    def compose_result_content(self) -> ComposeResult:
        yield Static(Group(*diff_lines(self.before, self.after)))


class MigrateResultScreen(CommandResultScreen):
    def __init__(self, command: click.Command, before: dict | None, after: dict) -> None:
        super().__init__(command)
        self.before = before
        self.after = after

    def compose_result_content(self) -> ComposeResult:
        yield Static(Group(*diff_lines(self.before, self.after)))


class _BaseMetadataScreen(Screen[None]):
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
        self._error: str | None = None
        self._status_panel = StatusPanel()
        self._pending_result: CommandResultScreen | None = None

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._required_frame is not None:
            refresh_required_subtitle(self._required_frame, self._field_specs)

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

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)
        self._status_panel.append_log(line)


class FixMetadataScreen(_BaseMetadataScreen):
    def __init__(self, command: click.Command) -> None:
        super().__init__(command)
        self._diff_log = RichLog(id="diff", auto_scroll=False)
        self._rich_view = TextArea(language="json", id="rich-view")
        self._before: dict | None = None

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
            yield Label("Diff (current vs. proposed)")
            yield self._diff_log
            yield Label("Proposed metadata (editable)")
            yield self._rich_view
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        super().on_input_changed(event)
        self._load_and_preview()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._refresh_diff()

    def _load_and_preview(self) -> None:
        assert self._path_field is not None
        path_str = self._path_field.value.strip()
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
        assert self._path_field is not None
        return f"ome-zarr-tools fix_metadata {self._path_field.value}".strip()

    def action_run(self) -> None:
        assert self._path_field is not None
        path_str = self._path_field.value.strip()
        if not path_str or not Path(path_str).exists():
            self._path_field.input.focus()
            self.notify("ZARR_PATH is required", severity="error")
            return
        proposed = self._current_proposed()
        if proposed is None:
            self.notify(self._error or "Invalid metadata", severity="error")
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        path = Path(path_str)
        group = zarr.open_group(path_str, mode="r+")
        after = proposed[0] if proposed else {}
        self._path_field.disabled = True
        self._rich_view.disabled = True

        def _work() -> None:
            write_metadata(path, group, proposed)

        result_screen = FixMetadataResultScreen(self.command, self._before, after)
        self._pending_result = result_screen
        self.app.push_screen(result_screen)
        on_progress, on_log = result_screen.begin()

        async def _on_done(result: ExecutionResult) -> None:
            self._pending_result = None
            assert self._path_field is not None
            self._path_field.disabled = False
            self._rich_view.disabled = False
            await result_screen.finish(result)

        run_in_background(
            self.app,
            _work,
            _on_done,
            on_progress=on_progress,
            on_log=on_log,
        )

    async def action_restore_defaults(self) -> None:
        if self._pending_result is not None:
            return
        await self.app.switch_screen(FixMetadataScreen(self.command))


class MigrateScreen(_BaseMetadataScreen):
    def __init__(self, command: click.Command) -> None:
        super().__init__(command)
        self._target_input = Input(value=DEFAULT_TARGET_VERSION, id="field-target_version")
        self._diff_log = RichLog(id="diff", auto_scroll=False)
        self._rich_view = TextArea(language="json", id="rich-view", read_only=True)
        self._before: dict | None = None

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
        super().on_input_changed(event)
        self._load_and_preview()

    def _load_and_preview(self) -> None:
        assert self._path_field is not None
        path_str = self._path_field.value.strip()
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
        assert self._path_field is not None
        return (
            f"ome-zarr-tools migrate {self._path_field.value} "
            f"--target_version {self._target_input.value}"
        ).strip()

    def action_run(self) -> None:
        assert self._path_field is not None
        path_str = self._path_field.value.strip()
        if not path_str or not Path(path_str).exists():
            self._path_field.input.focus()
            self.notify("ZARR_PATH is required", severity="error")
            return
        if self._error:
            self.notify(self._error, severity="error")
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        target_version = self._target_input.value.strip() or DEFAULT_TARGET_VERSION
        path = Path(path_str)
        source_version = detect_version(zarr.open_group(path_str, mode="r"))
        if source_version == target_version:
            self._append_log(f"{path_str} is already at version {target_version}; nothing to do.")
            self.notify("Already at target version; nothing to do.")
            return

        group = zarr.open_group(path_str, mode="r")
        after = json.loads(self._rich_view.text) if self._rich_view.text else {}
        self._path_field.disabled = True
        self._target_input.disabled = True

        def _work() -> None:
            apply_migration(path, group, target_version)

        result_screen = MigrateResultScreen(self.command, self._before, after)
        self._pending_result = result_screen
        self.app.push_screen(result_screen)
        on_progress, on_log = result_screen.begin()

        async def _on_done(result: ExecutionResult) -> None:
            self._pending_result = None
            assert self._path_field is not None
            self._path_field.disabled = False
            self._target_input.disabled = False
            await result_screen.finish(result)

        run_in_background(
            self.app,
            _work,
            _on_done,
            on_progress=on_progress,
            on_log=on_log,
        )

    async def action_restore_defaults(self) -> None:
        if self._pending_result is not None:
            return
        await self.app.switch_screen(MigrateScreen(self.command))
