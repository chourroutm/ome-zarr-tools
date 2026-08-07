"""T018/T019: live status indicator and log-toggle behavior (User Story 5).

Spec 004 US7 relocated this progress/log display from the prep screen to the
Command Result screen it navigates to on Run -- these tests patch
``StatusPanel`` at the class level (rather than grabbing a specific instance
via ``query_one``) since the Result screen's own ``StatusPanel`` instance
doesn't exist until *after* Run is pressed, and the callables `begin()` hands
to `run_command` are already-bound references by the time the test could
otherwise intercept them.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from textual.app import App
from textual.widgets import Input, OptionList

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import InteractiveTUIApp
from ome_zarr_tools.tui.screens.result_screen import CommandResultScreen
from ome_zarr_tools.tui.status import StatusPanel

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _menu_index(name: str) -> int:
    return sorted(COMMANDS).index(name)


async def _wait_for(pilot, predicate, attempts: int = 100) -> None:  # noqa: ANN001
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause()


class _StatusPanelApp(App):
    def on_mount(self) -> None:
        self.panel = StatusPanel()
        self.mount(self.panel)


async def test_status_panel_hidden_until_start_then_hidden_again_after_stop():
    """Sparkline/progress bar are hidden until start(), and hidden again after stop()."""
    app = _StatusPanelApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.panel
        assert panel._sparkline.display is False
        assert panel._progress.display is False

        panel.start()
        await pilot.pause()
        assert panel._sparkline.display is True
        assert panel._progress.display is False

        panel.update_progress(3, 10)
        await pilot.pause()
        assert panel._sparkline.display is False
        assert panel._progress.display is True
        assert panel._progress.progress == 3

        panel.stop()
        await pilot.pause()
        assert panel._sparkline.display is False
        assert panel._progress.display is False

        # A fresh start() after stop() goes back to indeterminate, not stuck quantified.
        panel.start()
        await pilot.pause()
        assert panel._sparkline.display is True
        assert panel._progress.display is False


async def test_dask_backed_command_status_transitions_to_quantified_progress(
    monkeypatch, tmp_path: Path, sample_ome_zarr, sample_mask_zarr
):
    """T018: apply_mask drives real dask work; the Result screen's status must switch
    Sparkline -> ProgressBar."""
    monkeypatch.chdir(tmp_path)

    progress_updates: list[tuple[int, int]] = []
    real_update_progress = StatusPanel.update_progress

    def spy_update_progress(self, done: int, total: int) -> None:  # noqa: ANN001
        progress_updates.append((done, total))
        real_update_progress(self, done, total)

    monkeypatch.setattr(StatusPanel, "update_progress", spy_update_progress)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("apply_mask")
        await pilot.press("enter")
        await pilot.pause()

        app.screen.query_one("#field-volume", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        app.screen.query_one("#field-mask", Input).focus()
        await pilot.press(*str(sample_mask_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        result_screen = app.screen
        assert isinstance(result_screen, CommandResultScreen)
        status_panel = result_screen._status_panel

        await _wait_for(pilot, lambda: result_screen._finished)

        assert len(progress_updates) > 1  # more than just the initial (0, total)
        totals = {total for _, total in progress_updates}
        assert totals == {progress_updates[0][1]}  # a single dask graph, one total
        assert [done for done, _ in progress_updates] == sorted(
            done for done, _ in progress_updates
        )  # monotonically non-decreasing
        assert progress_updates[-1][0] > 0  # real progress was made
        # Status hides again once the run finishes, whether it was quantified or not.
        assert status_panel._sparkline.display is False
        assert status_panel._progress.display is False
        assert "succeeded" in str(result_screen._outcome_label.content)


async def test_non_dask_command_status_stays_indeterminate(
    monkeypatch, tmp_path: Path, sample_ome_zarr
):
    """T018: inspect has no dask task graph; status must never quantify, always indeterminate."""
    monkeypatch.chdir(tmp_path)

    progress_updates: list[tuple[int, int]] = []
    real_update_progress = StatusPanel.update_progress

    def spy_update_progress(self, done: int, total: int) -> None:  # noqa: ANN001
        progress_updates.append((done, total))
        real_update_progress(self, done, total)

    monkeypatch.setattr(StatusPanel, "update_progress", spy_update_progress)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        app.screen.query_one("#field-zarr_path", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        result_screen = app.screen
        assert isinstance(result_screen, CommandResultScreen)
        status_panel = result_screen._status_panel

        await _wait_for(pilot, lambda: result_screen._finished)

        assert progress_updates == []  # no dask work -> never quantified
        # Status hides again once the run finishes.
        assert status_panel._progress.display is False
        assert status_panel._sparkline.display is False
        assert "succeeded" in str(result_screen._outcome_label.content)


async def test_log_toggle_does_not_pause_or_clear_captured_lines(
    monkeypatch, tmp_path: Path, sample_ome_zarr
):
    """T019: F8 toggling the Result screen's RichLog must not pause capture or clear
    already-captured lines."""
    monkeypatch.chdir(tmp_path)

    captured: list[str] = []
    real_append_log = StatusPanel.append_log

    def spy_append_log(self, line: str) -> None:  # noqa: ANN001
        captured.append(line)
        real_append_log(self, line)

    monkeypatch.setattr(StatusPanel, "append_log", spy_append_log)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        app.screen.query_one("#field-zarr_path", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        result_screen = app.screen
        assert isinstance(result_screen, CommandResultScreen)
        status_panel = result_screen._status_panel

        assert status_panel._log.display is False
        await pilot.press("f8")  # show the log
        await pilot.pause()
        assert status_panel._log.display is True

        await _wait_for(pilot, lambda: result_screen._finished)
        lines_after_run = list(captured)
        assert lines_after_run  # inspect's click.echo output was actually captured

        await pilot.press("f8")  # hide
        await pilot.pause()
        assert status_panel._log.display is False
        await pilot.press("f8")  # show again
        await pilot.pause()
        assert status_panel._log.display is True

    assert captured == lines_after_run  # toggling neither paused capture nor cleared it


async def test_captured_log_lines_match_direct_cli_output(
    monkeypatch, tmp_path: Path, sample_ome_zarr
):
    """T019: TUI-captured log lines must match what the equivalent direct CLI run prints."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    cli_result = runner.invoke(cli, ["inspect", str(sample_ome_zarr)])
    assert cli_result.exit_code == 0
    expected_text = cli_result.output.rstrip("\n")

    captured: list[str] = []
    real_append_log = StatusPanel.append_log

    def spy_append_log(self, line: str) -> None:  # noqa: ANN001
        captured.append(line)
        real_append_log(self, line)

    monkeypatch.setattr(StatusPanel, "append_log", spy_append_log)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        app.screen.query_one("#field-zarr_path", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()
        result_screen = app.screen
        assert isinstance(result_screen, CommandResultScreen)

        await _wait_for(pilot, lambda: result_screen._finished)

    assert "\n".join(captured) == expected_text
