"""fix_metadata/migrate screens: an argument-collecting Form, a Confirm screen
showing the suggested changes (auto mode for migrate, interactive mode for
fix_metadata), and a Result screen showing what was actually applied.

Neither command invokes its command via ``command.main()`` -- both commands have
an internal ``click.confirm``/``click.prompt`` gate that would hang on stdin
from a worker thread (research.md). Instead, the Confirm screen's Confirm
action calls each command's extracted, non-interactive write function directly
(``write_metadata``, ``apply_migration``), via the same worker-thread mechanism
every other command uses (``tui/execution.py``'s ``run_in_background``).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
import zarr
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label

from ome_zarr_tools.commands.fix_metadata import (
    PromptDefaults,
    build_proposed_multiscales,
    compute_default_prompt_values,
    parse_tuple_input,
    write_metadata,
)
from ome_zarr_tools.commands.migrate import (
    apply_migration,
    preview_migration,
    validate_chunks_per_shard,
)
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.io.ome_metadata import detect_version, read_multiscales
from ome_zarr_tools.tui.diff import build_side_by_side_diff
from ome_zarr_tools.tui.execution import ExecutionResult, run_in_background
from ome_zarr_tools.tui.fields import (
    FIELD_GAP_CLASS,
    FIELD_GAP_CSS,
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
        yield build_side_by_side_diff(self.before, self.after)


class MigrateResultScreen(CommandResultScreen):
    def __init__(self, command: click.Command, before: dict | None, after: dict) -> None:
        super().__init__(command)
        self.before = before
        self.after = after

    def compose_result_content(self) -> ComposeResult:
        yield build_side_by_side_diff(self.before, self.after)


class _BaseMetadataScreen(Screen[None]):
    """Shared chrome for the fix_metadata/migrate Form screens: just the
    argument-collecting fields -- Run navigates to a Confirm screen rather than
    executing directly (see ``_BaseConfirmScreen`` below)."""

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
        self.app.exit(result=self._invocation_text())

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)
        self._status_panel.append_log(line)


class FixMetadataScreen(_BaseMetadataScreen):
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
        self.app.push_screen(FixMetadataConfirmScreen(self.command, Path(path_str)))

    async def action_restore_defaults(self) -> None:
        await self.app.switch_screen(FixMetadataScreen(self.command))


class MigrateScreen(_BaseMetadataScreen):
    def __init__(self, command: click.Command) -> None:
        super().__init__(command)
        self._target_input: Input | None = None
        self._shard_input: Input | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            zarr_path_param = next(p for p in self.command.params if p.name == "zarr_path")
            target_version_param = next(
                p for p in self.command.params if p.name == "target_version"
            )
            chunks_per_shard_param = next(
                p for p in self.command.params if p.name == "chunks_per_shard"
            )
            path_spec = build_field_spec(zarr_path_param)
            assert isinstance(path_spec.widget, PathField)
            self._path_field = path_spec.widget
            target_spec = build_field_spec(target_version_param)
            assert isinstance(target_spec.widget, Input)
            self._target_input = target_spec.widget
            # --target_version has a CLI default (so click itself never requires it), but
            # this screen always shows it alongside ZARR_PATH -- grouping it in the same
            # Required frame keeps the two path/version fields the user reviews together
            # visually consistent, rather than tucking a pre-filled field into Optional.
            target_spec.required = True
            shard_spec = build_field_spec(chunks_per_shard_param)
            assert isinstance(shard_spec.widget, Input)
            self._shard_input = shard_spec.widget
            self._field_specs = [path_spec, target_spec, shard_spec]
            for frame in build_field_frames(self._field_specs):
                if frame.id == "required-frame":
                    self._required_frame = frame
                yield frame
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    def _invocation_text(self) -> str:
        assert self._path_field is not None
        assert self._target_input is not None
        assert self._shard_input is not None
        tokens = [
            f"ome-zarr-tools migrate {self._path_field.value}",
            f"--target_version {self._target_input.value}",
        ]
        shard_value = self._shard_input.value.strip()
        if shard_value:
            tokens.append(f"--chunks_per_shard {shard_value}")
        return " ".join(tokens).strip()

    def _parse_chunks_per_shard(self) -> tuple[int | None, str | None]:
        """Returns ``(value, error)`` -- ``value`` is ``None`` if the field is blank
        (no sharding requested) or parsing/validation failed, in which case
        ``error`` is a message ready to show the user."""
        assert self._shard_input is not None
        assert self._target_input is not None
        raw = self._shard_input.value.strip()
        if not raw:
            return None, None
        try:
            chunks_per_shard = int(raw)
        except ValueError:
            return None, "Chunks Per Shard must be a whole number"
        try:
            validate_chunks_per_shard(self._target_input.value.strip(), chunks_per_shard)
        except CliError as exc:
            return None, str(exc)
        return chunks_per_shard, None

    def action_run(self) -> None:
        assert self._path_field is not None
        assert self._target_input is not None
        path_str = self._path_field.value.strip()
        if not path_str or not Path(path_str).exists():
            self._path_field.input.focus()
            self.notify("ZARR_PATH is required", severity="error")
            return
        target_version = self._target_input.value.strip()
        if not target_version:
            self._target_input.focus()
            self.notify("Target Version is required", severity="error")
            return
        chunks_per_shard, error = self._parse_chunks_per_shard()
        if error is not None:
            assert self._shard_input is not None
            self._shard_input.focus()
            self.notify(error, severity="error")
            return
        self.app.push_screen(
            MigrateConfirmScreen(self.command, Path(path_str), target_version, chunks_per_shard)
        )

    async def action_restore_defaults(self) -> None:
        await self.app.switch_screen(MigrateScreen(self.command))


class _BaseConfirmScreen(Screen[None]):
    """Shared chrome for the fix_metadata/migrate Confirm screens: the same
    identity frame + bottom-bar template as Form/Result, a disabled field
    showing the ZARR_PATH collected on Form, and Confirm/Copy/Log/Back/Cancel
    shortcuts. ``escape``'s label is overridden to "Back to form" -- listed
    first, before ``shared_bindings()`` -- same technique verified for
    ``CommandResultScreen`` (research.md): Textual displays the first same-key
    binding's label while the action still fires once regardless."""

    BINDINGS = [
        Binding("escape", "back", "Back to form"),
        *shared_bindings(primary_label="Confirm"),
    ]

    DEFAULT_CSS = """
    #bottom-bar {
        dock: bottom;
        height: auto;
    }
    #confirm-diff {
        height: auto;
    }
    """

    def __init__(self, command: click.Command, zarr_path: Path) -> None:
        super().__init__()
        self.command = command
        self.zarr_path = zarr_path
        self._path_input = Input(value=str(zarr_path), id="confirm-path", disabled=True)
        self._log_lines: list[str] = []
        self._status_panel = StatusPanel()
        self._pending_result: CommandResultScreen | None = None

    def _invocation_text(self) -> str:
        raise NotImplementedError

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
        self.app.exit(result=self._invocation_text())

    def action_toggle_log(self) -> None:
        self._status_panel.toggle_log()

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)
        self._status_panel.append_log(line)


class FixMetadataConfirmScreen(_BaseConfirmScreen):
    """Interactive mode: a Rich-styled window of editable fields mirroring
    fix_metadata's CLI prompts (Image name, Spatial unit, Voxel size, Axis
    names), pre-filled with the same defaults the CLI's ``click.prompt()``
    calls show, with a live side-by-side diff updating as they're edited.
    Confirm writes and validates; Restore Defaults resets the fields."""

    BINDINGS = [
        *_BaseConfirmScreen.BINDINGS,
        Binding("f4", "restore_defaults", "Restore Defaults"),
    ]

    DEFAULT_CSS = (
        """
    #prompt-window {
        border: solid green;
        margin: 1;
        padding: 1;
        height: auto;
    }
    """
        + FIELD_GAP_CSS
    )

    def __init__(self, command: click.Command, zarr_path: Path) -> None:
        super().__init__(command, zarr_path)
        group = zarr.open_group(str(zarr_path), mode="r")
        multiscales = read_multiscales(group)
        self._before: dict | None = multiscales[0] if multiscales else None
        self._defaults: PromptDefaults = compute_default_prompt_values(multiscales)

        self._name_input = Input(
            value=self._defaults.name, id="prompt-name", classes=FIELD_GAP_CLASS
        )
        self._unit_input = Input(
            value=self._defaults.spatial_unit, id="prompt-unit", classes=FIELD_GAP_CLASS
        )
        self._voxel_input = Input(
            value=" ".join(str(v) for v in self._defaults.voxel_size),
            id="prompt-voxel",
            classes=FIELD_GAP_CLASS,
        )
        self._axes_input = Input(value=" ".join(self._defaults.axis_names), id="prompt-axes")
        self._diff_container = Vertical(id="confirm-diff")
        self._error: str | None = None
        self._restoring = False
        self._diff_lock = asyncio.Lock()

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            yield Label("ZARR_PATH")
            yield self._path_input
            prompt_window = Vertical(
                Label("Image name"),
                self._name_input,
                Label("Spatial unit"),
                self._unit_input,
                Label("Voxel size (z y x)"),
                self._voxel_input,
                Label("Axis names (space separated)"),
                self._axes_input,
                id="prompt-window",
            )
            prompt_window.border_title = "Prompts (fix_metadata)"
            yield prompt_window
            yield self._diff_container
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    async def on_mount(self) -> None:
        await self._refresh_diff()

    async def on_input_changed(self, event: Input.Changed) -> None:
        if self._restoring:
            return  # action_restore_defaults refreshes once itself, after setting all 4 fields
        if event.input in (self._name_input, self._unit_input, self._voxel_input, self._axes_input):
            await self._refresh_diff()

    def _current_proposed(self) -> list[dict] | None:
        try:
            voxel_size = parse_tuple_input(self._voxel_input.value, 3)
        except ValueError as exc:
            self._error = f"Invalid voxel size: {exc}"
            return None
        axis_names = [s.strip() for s in self._axes_input.value.replace(",", " ").split()][:3]
        if len(axis_names) != 3:
            axis_names = (axis_names + self._defaults.axis_names)[:3]
        self._error = None
        return build_proposed_multiscales(
            self._name_input.value.strip() or "Image",
            self._unit_input.value.strip() or "micrometer",
            voxel_size,
            axis_names,
            self._defaults.dataset_paths,
        )

    async def _refresh_diff(self) -> None:
        """Serialized via ``_diff_lock`` -- rapid successive calls (fast typing, or
        Restore Defaults setting 4 fields in a row) must not let one call's
        ``remove_children()``/``mount()`` interleave with another's, which would
        otherwise mount two ``#side-by-side-diff`` widgets (duplicate ID)."""
        async with self._diff_lock:
            proposed = self._current_proposed()
            after = proposed[0] if proposed else {}
            await self._diff_container.remove_children()
            await self._diff_container.mount(build_side_by_side_diff(self._before, after))

    def _invocation_text(self) -> str:
        return f"ome-zarr-tools fix_metadata {self.zarr_path}"

    async def action_restore_defaults(self) -> None:
        self._restoring = True
        self._name_input.value = self._defaults.name
        self._unit_input.value = self._defaults.spatial_unit
        self._voxel_input.value = " ".join(str(v) for v in self._defaults.voxel_size)
        self._axes_input.value = " ".join(self._defaults.axis_names)
        self._restoring = False
        await self._refresh_diff()

    def action_run(self) -> None:
        proposed = self._current_proposed()
        if proposed is None:
            self.notify(self._error or "Invalid input", severity="error")
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        group = zarr.open_group(str(self.zarr_path), mode="r+")
        after = proposed[0]
        for widget in (self._name_input, self._unit_input, self._voxel_input, self._axes_input):
            widget.disabled = True

        def _work() -> None:
            write_metadata(self.zarr_path, group, proposed)

        result_screen = FixMetadataResultScreen(self.command, self._before, after)
        self._pending_result = result_screen
        self.app.push_screen(result_screen)
        on_progress, on_log = result_screen.begin()

        async def _on_done(result: ExecutionResult) -> None:
            self._pending_result = None
            for widget in (self._name_input, self._unit_input, self._voxel_input, self._axes_input):
                widget.disabled = False
            await result_screen.finish(result)

        run_in_background(
            self.app,
            _work,
            _on_done,
            on_progress=on_progress,
            on_log=on_log,
        )


class MigrateConfirmScreen(_BaseConfirmScreen):
    """Auto mode: disabled ZARR_PATH field, then either an "already at target
    version" message or the side-by-side diff of what migrating would change.
    Confirm applies the migration; nothing to restore (nothing is editable
    here), so no Restore Defaults binding."""

    def __init__(
        self,
        command: click.Command,
        zarr_path: Path,
        target_version: str,
        chunks_per_shard: int | None = None,
    ) -> None:
        super().__init__(command, zarr_path)
        self.target_version = target_version
        self.chunks_per_shard = chunks_per_shard
        group = zarr.open_group(str(zarr_path), mode="r")
        self._before: dict = dict(group.attrs)
        self._source_version = detect_version(group)
        self._nothing_to_do = self._source_version == target_version
        self._after: dict = {}
        self._error: str | None = None
        if not self._nothing_to_do:
            try:
                self._after = preview_migration(zarr_path, target_version, chunks_per_shard)
            except Exception as exc:  # noqa: BLE001 -- surfaced via the status label, not raised
                self._error = str(exc)
        self._status_label = Label("", id="confirm-status")
        self._diff_container = Vertical(id="confirm-diff")

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield build_identity_frame(self.command)
            yield Label("ZARR_PATH")
            yield self._path_input
            yield self._status_label
            yield self._diff_container
        with Vertical(id="bottom-bar"):
            yield self._status_panel
            yield Footer()

    async def on_mount(self) -> None:
        if self._nothing_to_do:
            self._status_label.update(
                f"[green]✓ Already at version {self.target_version}; nothing to do.[/]"
            )
        elif self._error:
            self._status_label.update(f"[red]{self._error}[/]")
        else:
            status = f"Migrating from {self._source_version} to {self.target_version}"
            if self.chunks_per_shard is not None:
                status += f" (sharding: {self.chunks_per_shard} chunks/shard)"
            self._status_label.update(f"{status}:")
            await self._diff_container.mount(build_side_by_side_diff(self._before, self._after))

    def _invocation_text(self) -> str:
        tokens = f"ome-zarr-tools migrate {self.zarr_path} --target_version {self.target_version}"
        if self.chunks_per_shard is not None:
            tokens += f" --chunks_per_shard {self.chunks_per_shard}"
        return tokens

    def action_run(self) -> None:
        if self._nothing_to_do:
            self.notify("Already at target version; nothing to do.")
            return
        if self._error:
            self.notify(self._error, severity="error")
            return

        if self._pending_result is not None:
            self.app.push_screen(self._pending_result)
            return

        group = zarr.open_group(str(self.zarr_path), mode="r")

        def _work() -> None:
            apply_migration(self.zarr_path, group, self.target_version, self.chunks_per_shard)

        result_screen = MigrateResultScreen(self.command, self._before, self._after)
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
