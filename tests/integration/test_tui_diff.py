import zarr

from ome_zarr_tools.commands.fix_metadata import build_proposed_multiscales
from ome_zarr_tools.commands.migrate import preview_migration
from ome_zarr_tools.io.ome_metadata import read_multiscales
from ome_zarr_tools.tui.diff import build_side_by_side_diff


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


async def test_side_by_side_diff_has_current_and_proposed_panels():
    from textual.app import App
    from textual.screen import Screen
    from textual.widgets import Static

    class _Screen(Screen):
        def compose(self):
            yield build_side_by_side_diff({"a": 1}, {"a": 1, "b": 2})

    class _App(App):
        def on_mount(self) -> None:
            self.push_screen(_Screen())

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        panels = list(app.screen.query(Static))
        assert len(panels) == 2
        assert panels[0].border_title == "Current"
        assert panels[1].border_title == "Proposed"
        assert '"a": 1' in str(panels[0].content)
        assert '"b": 2' in str(panels[1].content)
        assert '"b": 2' not in str(panels[0].content)


async def test_side_by_side_diff_pads_shorter_side_to_keep_lines_aligned():
    """A replaced block with different line counts on each side (here the
    nested "a" object grows from 1 key to 3) must not leave the two panels'
    later, unchanged lines ("z": 9) on different rows."""
    from textual.app import App
    from textual.screen import Screen
    from textual.widgets import Static

    before = {"a": {"x": 1}, "z": 9}
    after = {"a": {"x": 1, "y": 2, "w": 3}, "z": 9}

    class _Screen(Screen):
        def compose(self):
            yield build_side_by_side_diff(before, after)

    class _App(App):
        def on_mount(self) -> None:
            self.push_screen(_Screen())

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        panels = list(app.screen.query(Static))
        left_lines = str(panels[0].content).splitlines()
        right_lines = str(panels[1].content).splitlines()
        assert len(left_lines) == len(right_lines)
        assert left_lines.index('  "z": 9') == right_lines.index('  "z": 9')


async def test_side_by_side_diff_no_before_shows_placeholder_on_current_panel():
    from textual.app import App
    from textual.screen import Screen
    from textual.widgets import Static

    class _Screen(Screen):
        def compose(self):
            yield build_side_by_side_diff(None, {"a": 1})

    class _App(App):
        def on_mount(self) -> None:
            self.push_screen(_Screen())

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        panels = list(app.screen.query(Static))
        assert "none" in str(panels[0].content).lower()
        assert '"a": 1' in str(panels[1].content)
