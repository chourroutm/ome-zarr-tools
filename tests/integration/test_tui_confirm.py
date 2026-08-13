"""fix_metadata/migrate's Confirm screen: Form's Run navigates here (not
directly executing); auto mode (migrate) shows a disabled path field plus
either "nothing to do" or the side-by-side diff; interactive mode
(fix_metadata) shows a Rich-styled window of editable fields mirroring the
CLI's prompts, with a live diff and Restore Defaults; Confirm executes and
pushes the existing Result screen."""

from __future__ import annotations

import zarr
from textual.app import App
from textual.widgets import Input

from ome_zarr_tools.cli import cli
from ome_zarr_tools.commands.fix_metadata import compute_default_prompt_values
from ome_zarr_tools.io.ome_metadata import read_multiscales
from ome_zarr_tools.tui.screens.metadata_screen import (
    FixMetadataConfirmScreen,
    FixMetadataResultScreen,
    FixMetadataScreen,
    MigrateConfirmScreen,
    MigrateResultScreen,
    MigrateScreen,
)

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


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


async def test_fix_metadata_form_run_navigates_to_confirm_screen(sample_ome_zarr):
    attrs_before = dict(zarr.open_group(str(sample_ome_zarr), mode="r").attrs)

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

    # Nothing was written yet -- Confirm is a separate, later action.
    attrs_after = dict(zarr.open_group(str(sample_ome_zarr), mode="r").attrs)
    assert attrs_after == attrs_before


async def test_fix_metadata_confirm_shows_disabled_path_and_prefilled_prompts(sample_ome_zarr):
    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    defaults = compute_default_prompt_values(read_multiscales(group))

    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#confirm-path", Input)
        assert path_input.disabled is True
        assert path_input.value == str(sample_ome_zarr)

        assert screen.query_one("#prompt-name", Input).value == defaults.name
        assert screen.query_one("#prompt-unit", Input).value == defaults.spatial_unit
        assert screen.query_one("#prompt-axes", Input).value == " ".join(defaults.axis_names)


async def test_fix_metadata_confirm_prompt_window_mirrors_required_frame_styling(sample_ome_zarr):
    """The Prompts window shares the Required frame's border style/spacing
    (solid border, 1-char margin/padding, size-to-content), but a different
    color (green, not red) to stay visually distinct."""
    from ome_zarr_tools.tui.fields import FIELD_GAP_CLASS

    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        prompt_window = screen.query_one("#prompt-window")
        assert prompt_window.styles.border_top[0] == "solid"
        assert prompt_window.styles.border_top[1].hex.lower() == "#008000"  # green, not red
        assert prompt_window.styles.height.is_auto
        from textual.geometry import Spacing

        assert prompt_window.styles.margin == Spacing(1, 1, 1, 1)
        assert prompt_window.styles.padding == Spacing(1, 1, 1, 1)

        # Blank-line spacing between fields uses the same shared CSS class as
        # the Required field-group frame -- present on all but the last field.
        for field_id in ("#prompt-name", "#prompt-unit", "#prompt-voxel"):
            widget = screen.query_one(field_id, Input)
            assert FIELD_GAP_CLASS in widget.classes
            assert widget.styles.margin == Spacing(0, 0, 1, 0)
        axes = screen.query_one("#prompt-axes", Input)
        assert FIELD_GAP_CLASS not in axes.classes


async def test_fix_metadata_confirm_screen_scrolls_not_a_nested_diff_region(sample_ome_zarr):
    """Overflow (long Current/Proposed panels, or a tall Prompts window) is
    handled by the Confirm screen's own outer scroll region -- not a nested,
    independently max-height-capped scrollable area, which cropped content
    instead of making it reachable."""
    from textual.containers import VerticalScroll

    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        outer_scroll = screen.query_one(VerticalScroll)
        assert outer_scroll.styles.overflow_y == "auto"

        diff_area = screen.query_one("#confirm-diff")
        assert diff_area.styles.max_height is None
        prompt_window = screen.query_one("#prompt-window")
        assert prompt_window.styles.max_height is None


async def test_migrate_confirm_diff_not_clipped_when_taller_than_viewport(legacy_v2_ome_zarr):
    """``Vertical``/``Horizontal`` default to ``height: 1fr; overflow: hidden
    hidden;`` -- without an explicit ``height: auto`` on #confirm-diff and the
    side-by-side diff's own Horizontal, a diff taller than the viewport was
    silently clipped instead of becoming reachable via the outer scroll."""
    app = _ScreenApp(lambda: MigrateConfirmScreen(COMMANDS["migrate"], legacy_v2_ome_zarr, "0.5"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        current_panel = app.screen.query_one("#diff-current")
        content_line_count = str(current_panel.content).count("\n")
        assert content_line_count > 24  # sanity: genuinely taller than the terminal
        assert current_panel.region.height >= content_line_count


async def test_side_by_side_diff_current_panel_left_margin_matches_proposed_right_margin():
    from textual.app import App
    from textual.geometry import Spacing
    from textual.screen import Screen

    from ome_zarr_tools.tui.diff import build_side_by_side_diff

    class _Screen(Screen):
        def compose(self):
            yield build_side_by_side_diff({"a": 1}, {"a": 1, "b": 2})

    class _DiffApp(App):
        def on_mount(self) -> None:
            self.push_screen(_Screen())

    app = _DiffApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        diff = app.screen.query_one("#side-by-side-diff")
        assert diff.styles.margin == Spacing(0, 1, 0, 1)  # left == right


async def test_fix_metadata_confirm_diff_updates_live_as_prompt_fields_edited(sample_ome_zarr):
    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        name_input = screen.query_one("#prompt-name", Input)
        name_input.focus()
        for _ in range(len(name_input.value)):
            await pilot.press("backspace")
        await pilot.press(*"RenamedImage")
        await pilot.pause()

        proposed_panel = screen.query_one("#diff-proposed")
        assert "RenamedImage" in str(proposed_panel.content)


async def test_fix_metadata_confirm_restore_defaults_resets_prompt_fields(sample_ome_zarr):
    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    defaults = compute_default_prompt_values(read_multiscales(group))

    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        name_input = screen.query_one("#prompt-name", Input)
        name_input.focus()
        for _ in range(len(name_input.value)):
            await pilot.press("backspace")
        await pilot.press(*"Changed")
        await pilot.pause()
        assert name_input.value == "Changed"

        await pilot.press("f4")
        await pilot.pause()

        assert screen.query_one("#prompt-name", Input).value == defaults.name


async def test_fix_metadata_confirm_invalid_voxel_size_blocks_confirm(sample_ome_zarr):
    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        voxel_input = screen.query_one("#prompt-voxel", Input)
        voxel_input.focus()
        for _ in range(len(voxel_input.value)):
            await pilot.press("backspace")
        await pilot.press(*"not numbers")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert app.screen is screen  # blocked, still on Confirm
        assert not isinstance(app.screen, FixMetadataResultScreen)


async def test_fix_metadata_confirm_confirm_writes_and_shows_result(sample_ome_zarr):
    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        name_input = screen.query_one("#prompt-name", Input)
        name_input.focus()
        for _ in range(len(name_input.value)):
            await pilot.press("backspace")
        await pilot.press(*"ConfirmedName")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, FixMetadataResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert "succeeded" in str(result_screen._outcome_label.content)

    written = zarr.open_group(str(sample_ome_zarr), mode="r").attrs["multiscales"]
    assert written[0]["name"] == "ConfirmedName"


async def test_fix_metadata_confirm_back_returns_to_form_with_path_preserved(sample_ome_zarr):
    app = _ScreenApp(lambda: FixMetadataScreen(COMMANDS["fix_metadata"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        form_screen = app.screen
        form_screen._path_field.input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()
        assert isinstance(app.screen, FixMetadataConfirmScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert app.screen is form_screen
        assert form_screen._path_field.value == str(sample_ome_zarr)


async def test_migrate_form_run_navigates_to_confirm_screen(legacy_v2_ome_zarr):
    app = _ScreenApp(lambda: MigrateScreen(COMMANDS["migrate"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._path_field.input.focus()
        await pilot.press(*str(legacy_v2_ome_zarr))
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, MigrateConfirmScreen)


async def test_migrate_form_chunks_per_shard_field_is_optional_and_blank(legacy_v2_ome_zarr):
    from textual.containers import Vertical

    app = _ScreenApp(lambda: MigrateScreen(COMMANDS["migrate"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        optional_frame = screen.query_one("#optional-frame", Vertical)
        assert screen._shard_input in optional_frame.query(Input)
        assert screen._shard_input.value == ""


async def test_migrate_form_blocks_run_when_sharding_requested_below_0_5(legacy_v2_ome_zarr):
    """FR: --chunks_per_shard requires --target_version 0.5+; the default target
    (0.4) plus a sharding value must block Run with a clear error, not navigate."""
    app = _ScreenApp(lambda: MigrateScreen(COMMANDS["migrate"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._path_field.input.focus()
        await pilot.press(*str(legacy_v2_ome_zarr))
        screen._shard_input.focus()
        await pilot.press(*"2")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert app.screen is screen  # blocked -- default target_version is 0.4


async def test_migrate_form_blocks_run_when_chunks_per_shard_not_a_number(legacy_v2_ome_zarr):
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
        screen._shard_input.focus()
        await pilot.press(*"not_a_number")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert app.screen is screen


async def test_migrate_form_run_passes_chunks_per_shard_to_confirm_screen(legacy_v2_ome_zarr):
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
        screen._shard_input.focus()
        await pilot.press(*"2")
        await pilot.pause()

        assert "--chunks_per_shard 2" in screen._invocation_text()

        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, MigrateConfirmScreen)
        assert app.screen.chunks_per_shard == 2
        assert "--chunks_per_shard 2" in app.screen._invocation_text()


async def test_migrate_confirm_applies_migration_with_sharding(legacy_v2_ome_zarr):
    app = _ScreenApp(
        lambda: MigrateConfirmScreen(COMMANDS["migrate"], legacy_v2_ome_zarr, "0.5", 2)
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, MigrateResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert "succeeded" in str(result_screen._outcome_label.content)

    migrated_group = zarr.open_group(str(legacy_v2_ome_zarr), mode="r")
    assert migrated_group.metadata.zarr_format == 3
    dataset_path = migrated_group.attrs["ome"]["multiscales"][0]["datasets"][0]["path"]
    assert migrated_group[dataset_path].shards is not None


async def test_migrate_confirm_nothing_to_do_shows_message_and_confirm_is_noop(
    legacy_v2_ome_zarr,
):
    from ome_zarr_tools.commands.migrate import DEFAULT_TARGET_VERSION

    app = _ScreenApp(
        lambda: MigrateConfirmScreen(
            COMMANDS["migrate"], legacy_v2_ome_zarr, DEFAULT_TARGET_VERSION
        )
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen._nothing_to_do is True
        assert "nothing to do" in str(screen._status_label.content).lower()
        assert len(screen.query("#diff-current")) == 0

        await pilot.press("f5")
        await pilot.pause()
        assert app.screen is screen  # Confirm is a no-op here, not an error


async def test_migrate_confirm_shows_diff_when_migration_needed(legacy_v2_ome_zarr):
    app = _ScreenApp(lambda: MigrateConfirmScreen(COMMANDS["migrate"], legacy_v2_ome_zarr, "0.5"))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen._nothing_to_do is False
        assert len(screen.query("#diff-current")) == 1
        assert len(screen.query("#diff-proposed")) == 1
        assert '"0.5"' in str(screen.query_one("#diff-proposed").content)


async def test_migrate_confirm_confirm_applies_migration_and_shows_result(legacy_v2_ome_zarr):
    app = _ScreenApp(lambda: MigrateConfirmScreen(COMMANDS["migrate"], legacy_v2_ome_zarr, "0.5"))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, MigrateResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert "succeeded" in str(result_screen._outcome_label.content)

    from ome_zarr_tools.io.ome_metadata import detect_version

    migrated_group = zarr.open_group(str(legacy_v2_ome_zarr), mode="r")
    assert detect_version(migrated_group) == "0.5"


async def test_migrate_confirm_back_returns_to_form_with_values_preserved(legacy_v2_ome_zarr):
    app = _ScreenApp(lambda: MigrateScreen(COMMANDS["migrate"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        form_screen = app.screen
        form_screen._path_field.input.focus()
        await pilot.press(*str(legacy_v2_ome_zarr))
        form_screen._target_input.focus()
        for _ in range(len(form_screen._target_input.value)):
            await pilot.press("backspace")
        await pilot.press(*"0.5")
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()
        assert isinstance(app.screen, MigrateConfirmScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert app.screen is form_screen
        assert form_screen._path_field.value == str(legacy_v2_ome_zarr)
        assert form_screen._target_input.value == "0.5"


async def test_confirm_screens_pending_guard_renavigates_instead_of_double_running(
    monkeypatch, sample_ome_zarr
):
    """Deferred fake write (never calls on_done) so the confirm stays pending;
    pressing Confirm again re-navigates to the same pending Result screen."""
    import ome_zarr_tools.tui.screens.metadata_screen as metadata_screen_module

    monkeypatch.setattr(
        metadata_screen_module,
        "run_in_background",
        lambda app, work, on_done, on_progress=None, on_log=None: None,
    )

    app = _ScreenApp(lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], sample_ome_zarr))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("f5")
        await pilot.pause()
        first_result_screen = app.screen
        assert isinstance(first_result_screen, FixMetadataResultScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is screen

        await pilot.press("f5")
        await pilot.pause()
        assert app.screen is first_result_screen  # same pending instance, not a new one
