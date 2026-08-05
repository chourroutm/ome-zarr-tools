"""T023/T026: specialized screens for `inspect` (US6) and `config` (US7)."""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import App
from textual.widgets import Input, TextArea

from ome_zarr_tools.commands.config import read_config, target_config_path
from ome_zarr_tools.commands.inspect import build_report
from ome_zarr_tools.tui.screens.config_screen import ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectScreen


class _InspectApp(App):
    def on_mount(self) -> None:
        self.push_screen(InspectScreen())


class _ConfigApp(App):
    def on_mount(self) -> None:
        self.push_screen(ConfigScreen())


async def _wait_for(pilot, predicate, attempts: int = 50) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause()


async def test_inspect_screen_panels_match_build_report_after_run(sample_ome_zarr):
    """T023: pressing Run builds the JSON-per-level and summary panels from build_report.

    Nothing is built just from typing the path -- inspect is no longer live
    (a remote gs://\\s3:// path would otherwise fire one network call per
    keystroke); only Run (F5) triggers a build.
    """
    expected = build_report(str(sample_ome_zarr))

    app = _InspectApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        # Typing alone must not have built anything yet.
        assert screen._report is None
        assert screen._log_lines == []

        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(screen._log_lines))

        for level in expected["levels"]:
            panel = screen.query_one(f"#json-level-{level['path']}", TextArea)
            assert json.loads(panel.text) == level

        summary = screen.query_one("#summary-view", TextArea)
        assert str(expected["total_stored_bytes"]) in summary.text
        assert str(expected["total_logical_bytes"]) in summary.text
        for level in expected["levels"]:
            assert str(tuple(level["shape"])) in summary.text
            assert str(tuple(level["chunk_shape"])) in summary.text


async def test_inspect_screen_run_twice_does_not_crash_on_duplicate_ids(sample_ome_zarr):
    """Regression: re-running must remove the old per-level panels before mounting new ones.

    ``remove_children()`` is async; firing the re-mount before it actually
    completed raised ``DuplicateIds`` on the second Run.
    """
    app = _InspectApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(screen._log_lines))
        assert len(screen._log_lines) == 1

        await pilot.press("f5")
        await _wait_for(pilot, lambda: len(screen._log_lines) > 1)

        assert all("succeeded" in line for line in screen._log_lines)
        panel = screen.query_one("#json-level-0", TextArea)
        assert json.loads(panel.text)["path"] == "0"


async def test_inspect_screen_switches_between_summary_and_json_panels(sample_ome_zarr):
    """T023: a keyboard shortcut switches between the two panels (tabbed, not simultaneous)."""
    app = _InspectApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_input = screen.query_one("#field-zarr_path", Input)
        path_input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()
        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(screen._log_lines))

        summary = screen.query_one("#summary-view", TextArea)
        json_panels = screen.query_one("#json-panels")

        assert summary.display is True
        assert json_panels.display is False

        await pilot.press("f9")
        await pilot.pause()
        assert summary.display is False
        assert json_panels.display is True

        await pilot.press("f9")
        await pilot.pause()
        assert summary.display is True
        assert json_panels.display is False


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
        await _wait_for(pilot, lambda: bool(screen._log_lines))

    assert any("succeeded" in line for line in screen._log_lines)


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
        assert json.loads(defaults.text)["target_version"] == "0.4"  # migrate's CLI default

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
    """T026: valid JSON save reproduces `config set`'s write; invalid JSON blocks it, edit kept."""
    monkeypatch.setenv("HOME", str(tmp_path))

    app = _ConfigApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        editor = screen.query_one("#editor", TextArea)

        editor.text = json.dumps({"compression": "zstd"}, indent=2)
        await pilot.pause()
        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(screen._log_lines))

        target_path = target_config_path(True, None)
        assert read_config(target_path) == {"compression": "zstd"}
        assert any("succeeded" in line for line in screen._log_lines)

        editor.text = "{not valid json"
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        # Blocked: no new log entry, file on disk unchanged, edit preserved verbatim.
        assert not any("succeeded" in line for line in screen._log_lines[1:])
        assert read_config(target_path) == {"compression": "zstd"}
        assert editor.text == "{not valid json"
