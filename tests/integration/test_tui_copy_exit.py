"""Spec 005: "Copy & exit" (F7) now exits with the CLI invocation as the
app's return value (`App[str | None]`, was always `App[None]`), so
commands/interactive.py can print it as a reliable fallback once the
clipboard-copy attempt (unchanged) may have silently failed -- e.g. OSC 52
not passed through a tmux/screen session. Every other exit path continues to
exit with a falsy result."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen
from ome_zarr_tools.tui.fields import PathField
from ome_zarr_tools.tui.screens.config_screen import ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectScreen
from ome_zarr_tools.tui.screens.metadata_screen import (
    FixMetadataConfirmScreen,
    FixMetadataScreen,
    MigrateConfirmScreen,
    MigrateScreen,
)

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


class _ScreenApp(App):
    def __init__(self, screen_factory) -> None:  # noqa: ANN001
        super().__init__()
        self._screen_factory = screen_factory

    def on_mount(self) -> None:
        self.push_screen(self._screen_factory())


async def test_inspect_screen_copy_and_exit_returns_invocation(sample_ome_zarr):
    app = _ScreenApp(lambda: InspectScreen(COMMANDS["inspect"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_field = screen.query_one(PathField)
        path_field.input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f7")
        await pilot.pause()

        assert app.return_value == screen._invocation_text()
        assert str(sample_ome_zarr) in app.return_value


async def test_generic_command_form_screen_copy_and_exit_returns_invocation():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["extract"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_field = screen.query_one(PathField)
        path_field.input.focus()
        await pilot.press(*"vol.zarr")
        await pilot.pause()

        await pilot.press("f7")
        await pilot.pause()

        assert app.return_value is not None
        assert "vol.zarr" in app.return_value
        assert app.return_value.startswith("ome-zarr-tools extract")


async def test_fix_metadata_form_screen_copy_and_exit_returns_invocation(sample_ome_zarr):
    app = _ScreenApp(lambda: FixMetadataScreen(COMMANDS["fix_metadata"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._path_field.input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f7")
        await pilot.pause()

        assert app.return_value == screen._invocation_text()
        assert str(sample_ome_zarr) in app.return_value


async def test_migrate_form_screen_copy_and_exit_returns_invocation(legacy_v2_ome_zarr):
    app = _ScreenApp(lambda: MigrateScreen(COMMANDS["migrate"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._path_field.input.focus()
        await pilot.press(*str(legacy_v2_ome_zarr))
        await pilot.pause()

        await pilot.press("f7")
        await pilot.pause()

        assert app.return_value == screen._invocation_text()
        assert "--target_version" in app.return_value


async def test_fix_metadata_confirm_screen_copy_and_exit_returns_invocation(sample_ome_zarr):
    app = _ScreenApp(
        lambda: FixMetadataConfirmScreen(COMMANDS["fix_metadata"], Path(sample_ome_zarr))
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        await pilot.press("f7")
        await pilot.pause()

        assert app.return_value == screen._invocation_text()
        assert str(sample_ome_zarr) in app.return_value


async def test_migrate_confirm_screen_copy_and_exit_returns_invocation(legacy_v2_ome_zarr):
    app = _ScreenApp(
        lambda: MigrateConfirmScreen(COMMANDS["migrate"], Path(legacy_v2_ome_zarr), "0.5")
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        await pilot.press("f7")
        await pilot.pause()

        assert app.return_value == screen._invocation_text()
        assert "--target_version 0.5" in app.return_value


async def test_config_screen_copy_and_exit_returns_invocation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = _ScreenApp(lambda: ConfigScreen(COMMANDS["config"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        await pilot.press("f7")
        await pilot.pause()

        assert app.return_value == screen._invocation_text()


async def test_plain_copy_does_not_exit_the_app():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["extract"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f6")  # Copy, not Copy & exit
        await pilot.pause()

        assert app.return_value is None
        assert isinstance(app.screen, CommandFormScreen)  # still on the same screen


async def test_other_exit_paths_still_return_falsy():
    """Cancel (menu) and a Confirm screen's own escape/back must not carry an
    invocation as the exit result -- only Copy & exit does."""
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["extract"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")  # Cancel
        await pilot.pause()

        assert app.return_value is None
