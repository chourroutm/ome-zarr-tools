"""Spec 007: `downsample`/`upsample` use the existing generic
`CommandFormScreen`/`GenericResultScreen` -- no specialized screen needed
(research.md). Both appear in the menu automatically once registered on the
CLI group (the TUI's command list is read straight from `cli.commands`)."""

from __future__ import annotations

from textual.widgets import Input, OptionList

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen, InteractiveTUIApp
from ome_zarr_tools.tui.fields import PathField
from ome_zarr_tools.tui.screens.result_screen import GenericResultScreen

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _menu_index(name: str) -> int:
    return sorted(COMMANDS).index(name)


async def _wait_for(pilot, predicate, attempts: int = 100) -> None:  # noqa: ANN001
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause()


async def test_downsample_appears_in_menu_and_uses_generic_form():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        option_list = app.screen.query_one(OptionList)
        assert option_list.get_option("downsample") is not None

        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("downsample")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, CommandFormScreen)
        screen = app.screen
        path_field = next(s.widget for s in screen._field_specs if isinstance(s.widget, PathField))
        assert path_field.input.id == "field-zarr_path"
        assert screen.query_one("#field-num_levels", Input).value == "1"
        assert screen.query_one("#field-output", Input).value == ""


async def test_downsample_run_executes_and_lands_on_generic_result_screen(sample_ome_zarr):
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("downsample")
        await pilot.press("enter")
        await pilot.pause()

        path_field = next(
            s.widget for s in app.screen._field_specs if isinstance(s.widget, PathField)
        )
        path_field.input.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, GenericResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert "succeeded" in str(result_screen._outcome_label.content)


async def test_upsample_appears_in_menu_and_uses_generic_form():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        option_list = app.screen.query_one(OptionList)
        assert option_list.get_option("upsample") is not None

        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("upsample")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, CommandFormScreen)
        screen = app.screen
        path_field = next(s.widget for s in screen._field_specs if isinstance(s.widget, PathField))
        assert path_field.input.id == "field-zarr_path"
        assert screen.query_one("#field-num_levels", Input).value == "1"
        assert screen.query_one("#field-smooth", Input).value == ""
        assert screen.query_one("#field-output", Input).value == ""


async def test_upsample_run_executes_and_lands_on_generic_result_screen(sample_mask_zarr):
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("upsample")
        await pilot.press("enter")
        await pilot.pause()

        path_field = next(
            s.widget for s in app.screen._field_specs if isinstance(s.widget, PathField)
        )
        path_field.input.focus()
        await pilot.press(*str(sample_mask_zarr))
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, GenericResultScreen)
        result_screen = app.screen
        await _wait_for(pilot, lambda: result_screen._finished)
        assert "succeeded" in str(result_screen._outcome_label.content)
