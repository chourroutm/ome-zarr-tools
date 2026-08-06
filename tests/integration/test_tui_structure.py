"""Spec 003 US3: every command screen shares the same structural skeleton --
one Header, one status/log region directly above the Footer, one Footer. The
command menu is exempt from the status/log region (it never runs a command)
but still shares the same Header/Footer chrome (contract rule 4).

Also spec 004 FR-002d: that shared Header shows a live clock everywhere.
"""

from __future__ import annotations

from textual.app import App
from textual.widgets import Footer, Header

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen, CommandMenuScreen
from ome_zarr_tools.tui.screens.config_screen import ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectScreen
from ome_zarr_tools.tui.screens.metadata_screen import FixMetadataScreen, MigrateScreen
from ome_zarr_tools.tui.status import StatusPanel

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


class _ScreenApp(App):
    def __init__(self, screen_factory) -> None:  # noqa: ANN001
        super().__init__()
        self._screen_factory = screen_factory

    def on_mount(self) -> None:
        self.push_screen(self._screen_factory())


async def _assert_skeleton(screen_factory) -> None:  # noqa: ANN001
    app = _ScreenApp(screen_factory)
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one(Header)
        assert len(app.screen.query(Header)) == 1
        assert len(app.screen.query(Footer)) == 1
        assert len(app.screen.query(StatusPanel)) == 1
        # Header(show_clock=...) has no public getter; Textual's own
        # attribute is `_show_clock` (spec 004 FR-002d).
        assert header._show_clock is True  # noqa: SLF001


async def test_command_form_screen_has_one_header_one_status_panel_one_footer():
    await _assert_skeleton(lambda: CommandFormScreen(COMMANDS["extract"]))


async def test_inspect_screen_has_one_header_one_status_panel_one_footer():
    await _assert_skeleton(InspectScreen)


async def test_fix_metadata_screen_has_one_header_one_status_panel_one_footer():
    await _assert_skeleton(FixMetadataScreen)


async def test_migrate_screen_has_one_header_one_status_panel_one_footer():
    await _assert_skeleton(MigrateScreen)


async def test_config_screen_has_one_header_one_status_panel_one_footer():
    await _assert_skeleton(ConfigScreen)


async def test_command_menu_screen_shares_header_footer_chrome_with_no_status_panel():
    app = _ScreenApp(lambda: CommandMenuScreen(COMMANDS))
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one(Header)
        assert len(app.screen.query(Header)) == 1
        assert len(app.screen.query(Footer)) == 1
        assert len(app.screen.query(StatusPanel)) == 0
        assert header._show_clock is True  # noqa: SLF001
