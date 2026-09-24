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
from ome_zarr_tools.commands.inspect import build_report
from ome_zarr_tools.core.env_file import read_env_file
from ome_zarr_tools.tui.screens.config_screen import (
    ConfigResultScreen,
    ConfigScreen,
    DefaultEntryButton,
)
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


def _default_button(screen, key: str) -> DefaultEntryButton:
    return next(b for b in screen._defaults_view.query(DefaultEntryButton) if b.default_key == key)


async def test_config_screen_default_buttons_are_registry_driven():
    """FR-010: the click-to-insert defaults are sourced from the
    `CONFIGURABLE_VARIABLES` registry (corrected variable names), not the old
    buggy per-option introspection that silently collided `extract`/`inspect`'s
    `output_format`."""
    app = _ConfigApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        button = _default_button(screen, "OME_ZARR_TOOLS_TARGET_VERSION")
        assert "OME_ZARR_TOOLS_TARGET_VERSION" in button.label.plain
        assert "0.5" in button.label.plain


async def test_config_screen_has_a_button_for_every_registry_variable():
    """Regression: every one of the 13 registry variables must have a
    clickable entry, including ones whose target option's own CLI default is
    `None` (--chunks_per_shard, --smooth) -- those default to "omit the flag"
    on the CLI, but are still legitimate configurable variables, and must not
    be silently dropped from the TUI's reference view."""
    from ome_zarr_tools.core.config_registry import CONFIGURABLE_VARIABLES

    app = _ConfigApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        button_keys = {b.default_key for b in screen._defaults_view.query(DefaultEntryButton)}
        assert button_keys == {v.name for v in CONFIGURABLE_VARIABLES}

        for name in ("OME_ZARR_TOOLS_CHUNKS_PER_SHARD", "OME_ZARR_TOOLS_UPSAMPLE_SMOOTH"):
            button = _default_button(screen, name)
            assert button.label.plain == f"{name}="  # blank value, not the literal "None"


async def test_config_screen_default_button_with_none_default_inserts_blank_value(
    tmp_path: Path,
):
    env_file = tmp_path / "settings.env"

    app = _ConfigApp()
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-env_file", Input)
        path_input.focus()
        await pilot.press(*str(env_file))
        await pilot.pause()

        editor = screen.query_one("#editor", TextArea)
        button = _default_button(screen, "OME_ZARR_TOOLS_CHUNKS_PER_SHARD")
        button.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(button)
        await pilot.pause()

        assert editor.text == "OME_ZARR_TOOLS_CHUNKS_PER_SHARD="  # not "...=None"


async def test_config_screen_default_button_inserts_key_value_line(tmp_path: Path):
    """Golden path: filling ENV_FILE and clicking a default-entry button
    inserts a plain `KEY=VALUE` line (not JSON) into the editor."""
    env_file = tmp_path / "settings.env"

    app = _ConfigApp()
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-env_file", Input)
        path_input.focus()
        await pilot.press(*str(env_file))
        await pilot.pause()

        editor = screen.query_one("#editor", TextArea)
        assert editor.text == ""

        button = _default_button(screen, "OME_ZARR_TOOLS_TARGET_VERSION")
        button.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(button)
        await pilot.pause()

        assert editor.text == "OME_ZARR_TOOLS_TARGET_VERSION=0.5"


async def test_config_screen_default_button_places_cursor_in_existing_value(tmp_path: Path):
    """Clicking a default that's already present in the editor leaves its
    current value untouched, just moving the cursor to its start -- rather
    than duplicating the key or erasing what's there."""
    app = _ConfigApp()
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        screen = app.screen
        editor = screen.query_one("#editor", TextArea)
        editor.text = "OME_ZARR_TOOLS_TARGET_VERSION=0.4"
        await pilot.pause()

        button = _default_button(screen, "OME_ZARR_TOOLS_TARGET_VERSION")
        button.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(button)
        await pilot.pause()

        assert editor.text == "OME_ZARR_TOOLS_TARGET_VERSION=0.4"  # untouched
        assert editor.cursor_location == (0, 30)  # right at the start of "0.4"


async def test_config_screen_save_writes_file_and_shows_plain_text_result(tmp_path: Path):
    """T022 golden path: Save writes the env-file to disk and navigates to
    `ConfigResultScreen`, which shows the plain-text content."""
    env_file = tmp_path / "settings.env"

    app = _ConfigApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        prep_screen = app.screen
        path_input = prep_screen.query_one("#field-env_file", Input)
        path_input.focus()
        await pilot.press(*str(env_file))
        await pilot.pause()

        editor = prep_screen.query_one("#editor", TextArea)
        editor.text = "OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.7"
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, ConfigResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)

        assert read_env_file(env_file) == ({"OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD": "0.7"}, [])
        assert "succeeded" in str(result_screen._outcome_label.content)
        assert result_screen.env_text == "OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.7\n"


async def test_config_screen_unrecognized_key_blocks_save(tmp_path: Path):
    """T022 edge case: an unrecognized `OME_ZARR_TOOLS_*` key in the editor
    blocks Save with an error notification; the file is never written and the
    editor content is preserved verbatim."""
    env_file = tmp_path / "settings.env"

    app = _ConfigApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        prep_screen = app.screen
        path_input = prep_screen.query_one("#field-env_file", Input)
        path_input.focus()
        await pilot.press(*str(env_file))
        await pilot.pause()

        editor = prep_screen.query_one("#editor", TextArea)
        editor.text = "OME_ZARR_TOOLS_TYPO_OPTION=1"
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        # Blocked: no navigation, file never written, edit preserved verbatim.
        assert app.screen is prep_screen
        assert not env_file.exists()
        assert editor.text == "OME_ZARR_TOOLS_TYPO_OPTION=1"
