"""T023/T026: specialized screens for `inspect` and `config`, plus their Result screens
(spec 004 US7 moved the always-post-Run content -- report panels, written config JSON --
off the prep screen and onto each command's own Result screen)."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from textual.app import App
from textual.widgets import Input, Static, TextArea

from ome_zarr_tools.cli import cli
from ome_zarr_tools.commands.config import read_config, target_config_path
from ome_zarr_tools.commands.inspect import build_report
from ome_zarr_tools.tui.screens.config_screen import ConfigResultScreen, ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectResultScreen, InspectScreen

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _render_to_text(renderable: object) -> str:
    """Plain-text rendering of a Rich renderable, for substring assertions
    against the Overview tab's Rich `Table`/`Text` content."""
    console = Console(record=True, width=200)
    console.print(renderable)
    return console.export_text()


class _InspectApp(App):
    def on_mount(self) -> None:
        self.push_screen(InspectScreen(COMMANDS["inspect"]))


class _ConfigApp(App):
    def on_mount(self) -> None:
        self.push_screen(ConfigScreen(COMMANDS["config"]))


async def _wait_for(pilot, predicate, attempts: int = 50) -> None:  # noqa: ANN001
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause()


async def test_inspect_screen_panels_match_build_report_after_run(sample_ome_zarr):
    """T023: pressing Run builds a "Level N" tab per pyramid level (Rich-formatted
    JSON, from build_report) plus an "Overview" tab on the Result screen -- nothing
    is built just from typing the path (inspect is no longer live; a remote
    gs://\\s3:// path would otherwise fire one network call per keystroke)."""
    expected = build_report(str(sample_ome_zarr))

    app = _InspectApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        # Typing alone must not have built anything, or navigated, yet.
        assert isinstance(app.screen, InspectScreen)

        await pilot.press("f5")
        await pilot.pause()
        assert isinstance(app.screen, InspectResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)

        for level in expected["levels"]:
            panel = result_screen.query_one(f"#json-level-{level['path']}", Static)
            assert json.loads(panel.content.text.plain) == level

        overview = result_screen.query_one("#overview-view", Static)
        overview_text = _render_to_text(overview.content)
        assert str(expected["total_stored_bytes"]) in overview_text
        assert str(expected["total_logical_bytes"]) in overview_text
        for level in expected["levels"]:
            assert str(tuple(level["shape"])) in overview_text
            assert str(tuple(level["chunk_shape"])) in overview_text
        assert expected["metadata_valid"] is True  # sanity: the version lines below only show then
        assert f"OME-NGFF version: {expected['ome_ngff_version']}" in overview_text
        assert f"Zarr version: {expected['zarr_version']}" in overview_text


async def test_inspect_result_screen_uses_tabs_with_rich_formatting(sample_ome_zarr):
    """The report is presented as tabs ("Overview", "Level 0", ...) instead of
    x+1 stacked panels, and each tab's content is a genuine Rich renderable
    (a colorized `rich.json.JSON`/`Table`), not plain unstyled text."""
    from rich.console import Group
    from rich.json import JSON
    from textual.widgets import TabbedContent, TabPane

    expected = build_report(str(sample_ome_zarr))

    app = _InspectApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)

        tabs = result_screen.query_one(TabbedContent)
        panes = {pane.id: str(pane._title) for pane in tabs.query(TabPane)}
        expected_ids = {"tab-overview", *(f"tab-level-{lvl['path']}" for lvl in expected["levels"])}
        assert set(panes) == expected_ids
        assert panes["tab-overview"] == "Overview"
        for level in expected["levels"]:
            assert panes[f"tab-level-{level['path']}"] == f"Level {level['path']}"

        overview = result_screen.query_one("#overview-view", Static)
        assert isinstance(overview.content, Group)  # Rich renderable, not a plain string
        for level in expected["levels"]:
            panel = result_screen.query_one(f"#json-level-{level['path']}", Static)
            assert isinstance(panel.content, JSON)  # syntax-highlighted, not plain text


async def test_inspect_screen_run_twice_in_a_row_does_not_crash(sample_ome_zarr):
    """Regression: Run -> Back to form -> Run again must produce two independently
    correct Result screens, not crash on duplicate widget IDs."""
    app = _InspectApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        prep_screen = app.screen
        path_input = prep_screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        first_result = app.screen
        await _wait_for(pilot, lambda: first_result._finished)
        assert "succeeded" in str(first_result._outcome_label.content)

        await pilot.press("escape")  # Back to form
        await pilot.pause()
        assert app.screen is prep_screen

        await pilot.press("f5")
        await pilot.pause()
        second_result = app.screen
        assert second_result is not first_result
        await _wait_for(pilot, lambda: second_result._finished)
        assert "succeeded" in str(second_result._outcome_label.content)

        panel = second_result.query_one("#json-level-0", Static)
        assert json.loads(panel.content.text.plain)["path"] == "0"


async def test_inspect_screen_run_executes_the_real_cli_command(sample_ome_zarr):
    app = _InspectApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        result_screen = app.screen
        assert isinstance(result_screen, InspectResultScreen)
        await _wait_for(pilot, lambda: result_screen._finished)

    assert "succeeded" in str(result_screen._outcome_label.content)


async def test_config_screen_current_and_defaults_match_scope(monkeypatch, tmp_path: Path):
    """T026: switching scope shows that scope's values (matching `config show`) and defaults."""
    monkeypatch.setenv("HOME", str(tmp_path))  # never touch the real shared $HOME on this host
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "ome-zarr-tools.config").write_text(
        json.dumps({"voxel_size_unit": "nanometer"}), encoding="utf-8"
    )

    app = _ConfigApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        # Default scope is "user"; no user config file exists yet.
        current = screen.query_one("#current-view", TextArea)
        assert json.loads(current.text) == {}
        defaults = screen.query_one("#defaults-view", TextArea)
        assert json.loads(defaults.text)["target_version"] == "0.5"  # migrate's CLI default

        screen._scope_select.value = "project"
        await pilot.pause()
        project_input = screen.query_one("#field-project_dir", Input)
        project_input.focus()
        await pilot.press(*str(project_dir))
        await pilot.pause()

        assert json.loads(current.text) == read_config(target_config_path(False, str(project_dir)))
        assert json.loads(current.text) == {"voxel_size_unit": "nanometer"}


async def test_config_screen_save_reproduces_config_set_and_blocks_invalid_json(
    monkeypatch, tmp_path: Path
):
    """T026: valid JSON save reproduces `config set`'s write, navigating to the Result
    screen; invalid JSON blocks it -- no navigation, edit kept verbatim."""
    monkeypatch.setenv("HOME", str(tmp_path))

    app = _ConfigApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        prep_screen = app.screen
        editor = prep_screen.query_one("#editor", TextArea)

        editor.text = json.dumps({"compression": "zstd"}, indent=2)
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, ConfigResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)

        target_path = target_config_path(True, None)
        assert read_config(target_path) == {"compression": "zstd"}
        assert "succeeded" in str(result_screen._outcome_label.content)
        assert json.loads(result_screen.config_json) == {"compression": "zstd"}

        await pilot.press("escape")  # Back to form
        await pilot.pause()
        assert app.screen is prep_screen

        editor.text = "{not valid json"
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        # Blocked: no navigation, file on disk unchanged, edit preserved verbatim.
        assert app.screen is prep_screen
        assert read_config(target_path) == {"compression": "zstd"}
        assert editor.text == "{not valid json"
