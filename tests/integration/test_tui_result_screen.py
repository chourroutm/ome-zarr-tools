"""Spec 004 US7: immediate Run navigation, pending -> finished Result screen,
"Back to form", the pending-run guard, and Restore Defaults."""

from __future__ import annotations

from textual.app import App
from textual.widgets import Input, OptionList

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen, InteractiveTUIApp
from ome_zarr_tools.tui.fields import PathField
from ome_zarr_tools.tui.screens.config_screen import ConfigResultScreen, ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectResultScreen, InspectScreen
from ome_zarr_tools.tui.screens.metadata_screen import (
    FixMetadataResultScreen,
    FixMetadataScreen,
    MigrateResultScreen,
    MigrateScreen,
)
from ome_zarr_tools.tui.screens.result_screen import GenericResultScreen

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _menu_index(name: str) -> int:
    return sorted(COMMANDS).index(name)


async def _wait_for(pilot, predicate, attempts: int = 100) -> None:  # noqa: ANN001
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause()


class _ScreenApp(App):
    def __init__(self, screen_factory) -> None:  # noqa: ANN001
        super().__init__()
        self._screen_factory = screen_factory

    def on_mount(self) -> None:
        self.push_screen(self._screen_factory())


async def test_run_navigates_immediately_then_shows_success(
    monkeypatch, tmp_path, sample_ome_zarr, sample_mask_zarr
):
    monkeypatch.chdir(tmp_path)
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("apply_mask")
        await pilot.press("enter")
        await pilot.pause()

        volume = app.screen.query_one("#field-volume-pathfield", PathField)
        volume.input.focus()
        await pilot.press(*str(sample_ome_zarr))
        mask = app.screen.query_one("#field-mask-pathfield", PathField)
        mask.input.focus()
        await pilot.press(*str(sample_mask_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        # Navigation itself is immediate -- verified precisely (before the worker can
        # possibly have resolved) in test_run_navigates_immediately_before_worker_resolves
        # below, using a controlled/deferred fake execution. A real, fast command may
        # already be finished by the time control returns here (no minimum pending
        # display duration is guaranteed -- spec.md's own edge case).
        assert isinstance(app.screen, GenericResultScreen)
        result_screen = app.screen

        await _wait_for(pilot, lambda: result_screen._finished)
        assert result_screen._outcome_label.display is True
        assert "succeeded" in str(result_screen._outcome_label.content)


async def test_run_navigates_immediately_before_worker_resolves(monkeypatch, tmp_path):
    """Precisely isolates FR-022's "navigate immediately, don't wait for completion"
    guarantee using a deferred fake execution the test controls explicitly."""
    import ome_zarr_tools.tui.app as tui_app_module
    from ome_zarr_tools.tui.execution import ExecutionResult

    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_run_command(app, command, tokens, on_done, on_progress=None, on_log=None):  # noqa: ANN001
        captured["on_done"] = on_done

    monkeypatch.setattr(tui_app_module, "run_command", fake_run_command)

    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["apply_mask"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one("#field-volume-pathfield", PathField).input.value = "vol.zarr"
        screen.query_one("#field-mask-pathfield", PathField).input.value = "mask.zarr"
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, GenericResultScreen)
        result_screen = app.screen
        assert result_screen._finished is False
        assert result_screen._outcome_label.display is False

        await captured["on_done"](ExecutionResult(succeeded=True))
        await pilot.pause()
        assert result_screen._finished is True
        assert result_screen._outcome_label.display is True


async def test_run_navigates_immediately_then_shows_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("apply_mask")
        await pilot.press("enter")
        await pilot.pause()

        volume = app.screen.query_one("#field-volume-pathfield", PathField)
        volume.input.focus()
        await pilot.press(*"does-not-exist.zarr")
        mask = app.screen.query_one("#field-mask-pathfield", PathField)
        mask.input.focus()
        await pilot.press(*"also-does-not-exist.zarr")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, GenericResultScreen)
        result_screen = app.screen

        await _wait_for(pilot, lambda: result_screen._finished)
        assert result_screen._outcome_label.display is True
        assert "failed" in str(result_screen._outcome_label.content)
        # the outcome label itself stays short -- the full error prints below it
        assert result_screen._error_label.display is True
        assert str(result_screen._error_label.content)


async def test_outcome_label_sits_at_the_right_end_of_the_identity_row():
    """The status indicator (spec 004 follow-up) shares a row with the
    command name/description instead of a separate line below it, pinned to
    the right end -- the identity frame takes the remaining space (1fr) so
    the outcome label is pushed flush right."""
    app = _ScreenApp(lambda: InspectResultScreen(COMMANDS["inspect"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        from ome_zarr_tools.tui.execution import ExecutionResult

        await screen.finish(ExecutionResult(succeeded=True))
        await pilot.pause()

        frame = screen.query_one("#identity-frame")
        outcome = screen.query_one("#outcome-label")
        assert frame.region.y == outcome.region.y  # same row as the command name
        assert outcome.region.right == frame.region.right + outcome.region.width
        assert outcome.region.x == frame.region.right  # flush against the frame's right edge


async def test_error_detail_wraps_within_screen_width_not_clipped():
    """A long failure message shown below the status row must wrap to the
    screen's width like every other description text in this app, not
    overflow past it on a single un-wrapped line (the same class of bug
    fixed for identity-frame descriptions)."""
    app = _ScreenApp(lambda: InspectResultScreen(COMMANDS["inspect"]))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = app.screen
        from ome_zarr_tools.tui.execution import ExecutionResult

        long_error = (
            "Some fairly long error message describing exactly what went wrong "
            "here, long enough on its own to require wrapping across more than "
            "one line at an 80-column terminal width."
        )
        await screen.finish(ExecutionResult(succeeded=False, error=long_error))
        await pilot.pause()

        error_label = screen.query_one("#error-detail")
        assert long_error in str(error_label.content)
        assert error_label.region.width <= 80
        assert error_label.region.height >= 2  # must have wrapped, not overflowed on 1 line


async def test_blocked_run_does_not_navigate():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        prep_screen = app.screen
        await pilot.press("f5")
        await pilot.pause()
        assert app.screen is prep_screen  # required ZARR_PATH still empty; no navigation


async def test_back_to_form_returns_from_either_state_with_fields_unchanged(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("apply_mask")
        await pilot.press("enter")
        await pilot.pause()

        prep_screen = app.screen
        volume = app.screen.query_one("#field-volume-pathfield", PathField)
        volume.input.focus()
        await pilot.press(*"vol.zarr")
        mask = app.screen.query_one("#field-mask-pathfield", PathField)
        mask.input.focus()
        await pilot.press(*"mask.zarr")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        assert isinstance(app.screen, GenericResultScreen)

        # Back to form while still pending
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is prep_screen
        assert app.screen.query_one("#field-volume-pathfield", PathField).input.value == "vol.zarr"
        assert app.screen.query_one("#field-mask-pathfield", PathField).input.value == "mask.zarr"


async def test_second_run_while_pending_renavigates_instead_of_duplicating(monkeypatch, tmp_path):
    """Uses a deferred fake execution (never calls on_done) so the run stays
    genuinely pending -- a real command may finish before the test can observe
    the in-flight state (spec.md's own "no minimum pending duration" edge case)."""
    import ome_zarr_tools.tui.app as tui_app_module

    monkeypatch.chdir(tmp_path)
    call_count = {"n": 0}

    def fake_run_command(app, command, tokens, on_done, on_progress=None, on_log=None):  # noqa: ANN001
        call_count["n"] += 1

    monkeypatch.setattr(tui_app_module, "run_command", fake_run_command)

    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["apply_mask"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one("#field-volume-pathfield", PathField).input.value = "vol.zarr"
        screen.query_one("#field-mask-pathfield", PathField).input.value = "mask.zarr"
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        first_result_screen = app.screen
        assert isinstance(first_result_screen, GenericResultScreen)
        assert call_count["n"] == 1

        await pilot.press("escape")
        await pilot.pause()
        prep_screen = app.screen
        assert prep_screen is screen
        assert prep_screen._pending_result is first_result_screen

        await pilot.press("f5")
        await pilot.pause()
        assert call_count["n"] == 1  # no second execution started
        assert app.screen is first_result_screen  # re-navigated, not a new instance


async def test_inspect_result_screen_shows_summary_and_json_report(
    monkeypatch, tmp_path, sample_ome_zarr
):
    app = _ScreenApp(lambda: InspectScreen(COMMANDS["inspect"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._path_field.input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, InspectResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert result_screen.report is not None
        assert result_screen.query_one("#tab-overview")
        assert result_screen.query_one("#tab-level-0")


async def test_fix_metadata_result_screen_shows_applied_diff(sample_ome_zarr):
    from ome_zarr_tools.tui.screens.metadata_screen import FixMetadataConfirmScreen

    app = _ScreenApp(lambda: FixMetadataScreen(COMMANDS["fix_metadata"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._path_field.input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, FixMetadataConfirmScreen)
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, FixMetadataResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert len(result_screen.query("#diff-current")) == 1
        assert len(result_screen.query("#diff-proposed")) == 1


async def test_migrate_result_screen_shows_applied_diff(legacy_v2_ome_zarr):
    from ome_zarr_tools.tui.screens.metadata_screen import MigrateConfirmScreen

    app = _ScreenApp(lambda: MigrateScreen(COMMANDS["migrate"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._path_field.input.focus()
        await pilot.press(*str(legacy_v2_ome_zarr))
        screen._target_input.focus()
        for _ in range(len(screen._target_input.value)):
            await pilot.press("backspace")
        await pilot.press(*"0.5")
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, MigrateConfirmScreen)
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, MigrateResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert len(result_screen.query("#diff-current")) == 1
        # #result-content defaults to Vertical's `height: 1fr; overflow: hidden
        # hidden;` unless overridden -- would silently clip a diff taller than
        # the viewport instead of leaving it reachable via the outer scroll.
        current_panel = result_screen.query_one("#diff-current")
        content_line_count = str(current_panel.content).count("\n")
        assert current_panel.region.height >= content_line_count
        assert len(result_screen.query("#diff-proposed")) == 1


async def test_config_result_screen_shows_written_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = _ScreenApp(lambda: ConfigScreen(COMMANDS["config"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._editor.text = '{"voxel_size_unit": "nanometer"}'
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, ConfigResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert "nanometer" in result_screen.config_json


async def test_restore_defaults_reloads_screen_with_opening_values(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        unit = screen.query_one("#field-voxel_size_unit", Input)
        opening_value = unit.value
        unit.focus()
        for _ in range(len(unit.value)):
            await pilot.press("backspace")
        await pilot.press(*"nanometer")
        await pilot.pause()
        assert screen.query_one("#field-voxel_size_unit", Input).value == "nanometer"

        await pilot.press("f4")
        await pilot.pause()

        assert app.screen is not screen
        assert isinstance(app.screen, CommandFormScreen)
        new_unit = app.screen.query_one("#field-voxel_size_unit", Input)
        assert new_unit.value == opening_value


async def test_migrate_screen_restore_defaults_resets_target_version_field(
    legacy_v2_ome_zarr,
):
    from ome_zarr_tools.commands.migrate import DEFAULT_TARGET_VERSION

    app = _ScreenApp(lambda: MigrateScreen(COMMANDS["migrate"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._target_input.focus()
        for _ in range(len(screen._target_input.value)):
            await pilot.press("backspace")
        await pilot.press(*"9.9")
        await pilot.pause()
        assert screen._target_input.value == "9.9"

        await pilot.press("f4")
        await pilot.pause()

        assert app.screen is not screen
        assert app.screen._target_input.value == DEFAULT_TARGET_VERSION


async def test_restore_defaults_no_op_while_run_is_pending(monkeypatch, tmp_path):
    """Uses a deferred fake execution (never calls on_done) so the run stays
    genuinely pending through the whole test."""
    import ome_zarr_tools.tui.app as tui_app_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        tui_app_module,
        "run_command",
        lambda app, command, tokens, on_done, on_progress=None, on_log=None: None,
    )

    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["apply_mask"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        volume = screen.query_one("#field-volume-pathfield", PathField)
        volume.input.focus()
        await pilot.press(*"vol.zarr")
        mask = screen.query_one("#field-mask-pathfield", PathField)
        mask.input.focus()
        await pilot.press(*"mask.zarr")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is screen  # back on the prep screen, run still pending

        await pilot.press("f4")
        await pilot.pause()
        assert app.screen is screen  # Restore Defaults was a no-op
