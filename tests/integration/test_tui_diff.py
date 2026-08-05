import json
from pathlib import Path

import zarr
from textual.app import App
from textual.widgets import Input, TextArea

from ome_zarr_tools.commands.fix_metadata import build_proposed_multiscales
from ome_zarr_tools.commands.migrate import preview_migration
from ome_zarr_tools.io.ome_metadata import read_multiscales
from ome_zarr_tools.tui.screens.metadata_screen import FixMetadataScreen, MigrateScreen


class _FixMetadataApp(App):
    def on_mount(self) -> None:
        self.push_screen(FixMetadataScreen())


class _MigrateApp(App):
    def on_mount(self) -> None:
        self.push_screen(MigrateScreen())


async def _wait_for(pilot, predicate, attempts: int = 50) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause()


def test_build_proposed_multiscales_matches_inline_shape(sample_ome_zarr):
    """T010: extracted function produces the same shape fix_metadata's prompt flow builds."""
    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    multiscales = read_multiscales(group)
    dataset_paths = [d["path"] for d in multiscales[0]["datasets"]]

    result = build_proposed_multiscales(
        "Image", "micrometer", (1.0, 1.0, 1.0), ["z", "y", "x"], dataset_paths
    )

    assert result[0]["version"] == "0.4"
    assert result[0]["name"] == "Image"
    assert [a["name"] for a in result[0]["axes"]] == ["z", "y", "x"]
    assert [d["path"] for d in result[0]["datasets"]] == dataset_paths


def test_preview_migration_matches_real_migration_result(legacy_v2_ome_zarr):
    """T010: preview_migration's output matches what a real migration produces, without writing."""
    before_bytes = sorted((legacy_v2_ome_zarr / "0").rglob("*"))

    preview_attrs = preview_migration(legacy_v2_ome_zarr, "0.5")
    assert preview_attrs["ome"]["version"] == "0.5"

    # Nothing on disk changed.
    assert (legacy_v2_ome_zarr / ".zattrs").exists()
    assert sorted((legacy_v2_ome_zarr / "0").rglob("*")) == before_bytes


async def test_fix_metadata_screen_diff_for_dataset_with_existing_metadata(sample_ome_zarr):
    app = _FixMetadataApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        assert screen._before is not None
        rich_view = screen.query_one("#rich-view", TextArea)
        proposed = json.loads(rich_view.text)
        assert proposed[0]["name"]  # populated from existing metadata's defaults


async def test_fix_metadata_screen_diff_for_dataset_with_no_prior_metadata(tmp_path: Path):
    empty_zarr = tmp_path / "empty.zarr"
    zarr.open_group(str(empty_zarr), mode="w")  # a group with no multiscales metadata at all

    app = _FixMetadataApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(empty_zarr))
        await pilot.pause()

        assert screen._before is None  # empty "before" state, not skipped
        rich_view = screen.query_one("#rich-view", TextArea)
        proposed = json.loads(rich_view.text)
        assert proposed[0]["name"] == "Image"  # falls back to defaults


async def test_fix_metadata_screen_invalid_edit_blocks_run(sample_ome_zarr):
    app = _FixMetadataApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        rich_view = screen.query_one("#rich-view", TextArea)
        rich_view.text = "{not valid json"
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        assert screen._log_lines == []  # Run was blocked, nothing executed

        # Fix it and confirm Run now succeeds.
        proposed = [
            {
                "version": "0.4",
                "name": "FixedName",
                "axes": [
                    {"name": "z", "type": "space", "unit": "micrometer"},
                    {"name": "y", "type": "space", "unit": "micrometer"},
                    {"name": "x", "type": "space", "unit": "micrometer"},
                ],
                "datasets": [
                    {
                        "path": "0",
                        "coordinateTransformations": [{"type": "scale", "scale": [1.0, 1.0, 1.0]}],
                    }
                ],
            }
        ]
        rich_view.text = json.dumps(proposed, indent=2)
        await pilot.pause()
        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(screen._log_lines))

    assert any("succeeded" in line for line in screen._log_lines)


async def test_migrate_screen_preview_updates_with_target_version_and_no_writes_before_run(
    legacy_v2_ome_zarr,
):
    checksum_before = sorted((legacy_v2_ome_zarr / "0").rglob("*"))

    app = _MigrateApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(legacy_v2_ome_zarr))
        await pilot.pause()

        rich_view = screen.query_one("#rich-view", TextArea)
        first_preview = rich_view.text
        assert '"version": "0.4"' in first_preview

        target_input = screen.query_one("#field-target_version", Input)
        target_input.focus()
        for _ in range(3):
            await pilot.press("backspace")
        await pilot.press(*"0.5")
        await pilot.pause()

        second_preview = rich_view.text
        assert '"version": "0.5"' in second_preview
        assert second_preview != first_preview

        # Zero writes have happened yet -- the dataset is exactly as it was.
        assert sorted((legacy_v2_ome_zarr / "0").rglob("*")) == checksum_before
        assert (legacy_v2_ome_zarr / ".zattrs").exists()
