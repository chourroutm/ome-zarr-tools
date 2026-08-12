"""Spec 004 US1: the command menu screen's logo + 3-line Rich menu entries."""

from __future__ import annotations

import click
from rich.console import Group
from textual.widgets import OptionList

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandMenuScreen, InteractiveTUIApp
from ome_zarr_tools.tui.fields import command_description
from ome_zarr_tools.tui.logo import LOGO_MIN_HEIGHT, LOGO_MIN_WIDTH, Logo

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _prompt_lines(prompt: object) -> list[str]:
    assert isinstance(prompt, Group)
    return [renderable.plain for renderable in prompt.renderables]


async def test_menu_shows_logo_above_option_list():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CommandMenuScreen)
        logo = screen.query_one(Logo)
        option_list = screen.query_one(OptionList)
        widgets = list(screen.walk_children())
        assert widgets.index(logo) < widgets.index(option_list)


async def test_menu_option_prompt_is_3_lines_with_name_and_command_help():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        option_list = app.screen.query_one(OptionList)
        first_name = sorted(COMMANDS)[0]
        option = option_list.get_option(first_name)
        lines = _prompt_lines(option.prompt)
        assert len(lines) == 3
        assert first_name in lines[0]
        assert command_description(COMMANDS[first_name]) in lines[1]
        assert lines[2] == ""


async def test_menu_option_prompt_long_description_is_overflow_hidden_not_truncated():
    """apply_mask's help text is long enough to exceed a typical terminal
    width; the full text is kept (never character-truncated with "..."),
    with Rich's own overflow="crop" clipping it visually at render time."""
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        option_list = app.screen.query_one(OptionList)
        option = option_list.get_option("apply_mask")
        lines = _prompt_lines(option.prompt)
        full_help = command_description(COMMANDS["apply_mask"])
        assert len(full_help) > 70  # sanity: long enough that a limit=70 cutoff would bite
        assert full_help in lines[1]
        assert not lines[1].endswith("...")

        description = option.prompt.renderables[1]
        assert description.no_wrap is True
        assert description.overflow == "crop"


async def test_menu_option_prompt_not_cut_at_abbreviation_period():
    """``inspect``'s help text contains the abbreviation "vs.", which
    ``click.Command.get_short_help_str()`` misidentifies as a sentence
    boundary and truncates at -- silently, with no ellipsis -- regardless of
    the ``limit`` passed in. The menu entry must show the text past that
    point too."""
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        option_list = app.screen.query_one(OptionList)
        option = option_list.get_option("inspect")
        lines = _prompt_lines(option.prompt)
        assert "logical size" in lines[1]  # the part click's heuristic used to cut off


async def test_menu_option_prompt_blank_second_line_for_command_with_no_help():
    no_help_command = click.Command(name="no_help", callback=lambda: None, help=None)
    commands = {**COMMANDS, "no_help": no_help_command}
    app = InteractiveTUIApp(commands)
    async with app.run_test() as pilot:
        await pilot.pause()
        option_list = app.screen.query_one(OptionList)
        option = option_list.get_option("no_help")
        lines = _prompt_lines(option.prompt)
        assert lines[1].strip() == ""


async def test_menu_resize_toggles_logo_visibility():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        logo = app.screen.query_one(Logo)
        assert logo.display is True

        await pilot.resize_terminal(LOGO_MIN_WIDTH - 1, LOGO_MIN_HEIGHT - 1)
        await pilot.pause()
        assert logo.display is False

        await pilot.resize_terminal(80, 30)
        await pilot.pause()
        assert logo.display is True
