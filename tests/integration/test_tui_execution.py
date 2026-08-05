"""T018/T019: live status indicator and log-toggle behavior (User Story 5)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from textual.app import App
from textual.widgets import Input, OptionList

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import InteractiveTUIApp
from ome_zarr_tools.tui.status import StatusPanel

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _menu_index(name: str) -> int:
    return sorted(COMMANDS).index(name)


async def _wait_for(pilot, predicate, attempts: int = 100) -> None:
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
    """T018: apply_mask drives real dask work; status must switch Sparkline -> ProgressBar."""
    monkeypatch.chdir(tmp_path)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("apply_mask")
        await pilot.press("enter")
        await pilot.pause()

        form_screen = app.screen
        status_panel = form_screen.query_one(StatusPanel)
        assert status_panel._quantified is False

        # Spy on update_progress: dask task graphs can contain already-resolved
        # keys that never fire `posttask`, so `done` isn't guaranteed to reach
        # `total` exactly (verified directly against apply_mask's real graph) --
        # what matters is that real, increasing progress was observed.
        progress_updates: list[tuple[int, int]] = []
        real_update_progress = status_panel.update_progress

        def spy_update_progress(done: int, total: int) -> None:
            progress_updates.append((done, total))
            real_update_progress(done, total)

        status_panel.update_progress = spy_update_progress  # type: ignore[method-assign]

        app.screen.query_one("#field-volume", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        app.screen.query_one("#field-mask", Input).focus()
        await pilot.press(*str(sample_mask_zarr))
        await pilot.pause()

        assert status_panel._sparkline.display is False  # hidden until Run is pressed
        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(form_screen._log_lines))

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
    assert any("succeeded" in line for line in form_screen._log_lines)


async def test_non_dask_command_status_stays_indeterminate(
    monkeypatch, tmp_path: Path, sample_ome_zarr
):
    """T018: inspect has no dask task graph; status must never quantify, always indeterminate."""
    monkeypatch.chdir(tmp_path)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        form_screen = app.screen
        status_panel = form_screen.query_one(StatusPanel)
        progress_updates: list[tuple[int, int]] = []
        real_update_progress = status_panel.update_progress
        status_panel.update_progress = lambda done, total: (  # type: ignore[method-assign]
            progress_updates.append((done, total)),
            real_update_progress(done, total),
        )[1]

        app.screen.query_one("#field-zarr_path", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        assert status_panel._sparkline.display is False  # hidden until Run is pressed
        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(form_screen._log_lines))

        assert progress_updates == []  # no dask work -> never quantified
        # Status hides again once the run finishes.
        assert status_panel._progress.display is False
        assert status_panel._sparkline.display is False
    assert any("succeeded" in line for line in form_screen._log_lines)


async def test_log_toggle_does_not_pause_or_clear_captured_lines(
    monkeypatch, tmp_path: Path, sample_ome_zarr
):
    """T019: F8 toggling the RichLog must not pause capture or clear already-captured lines."""
    monkeypatch.chdir(tmp_path)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        form_screen = app.screen
        status_panel = form_screen.query_one(StatusPanel)
        captured: list[str] = []
        real_append_log = status_panel.append_log
        status_panel.append_log = lambda line: (captured.append(line), real_append_log(line))[1]  # type: ignore[method-assign]

        app.screen.query_one("#field-zarr_path", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        assert status_panel._log.display is False
        await pilot.press("f8")  # show the log before the run starts
        await pilot.pause()
        assert status_panel._log.display is True

        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(form_screen._log_lines))
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

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        form_screen = app.screen
        status_panel = form_screen.query_one(StatusPanel)
        captured: list[str] = []
        real_append_log = status_panel.append_log
        status_panel.append_log = lambda line: (captured.append(line), real_append_log(line))[1]  # type: ignore[method-assign]

        app.screen.query_one("#field-zarr_path", Input).focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(form_screen._log_lines))

    assert "\n".join(captured) == expected_text
