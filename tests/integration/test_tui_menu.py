"""Spec 004 US1: the command menu screen's logo + 3-line Rich menu entries."""

from __future__ import annotations

import click
from rich.console import Group
from textual.widgets import Input, OptionList, TextArea

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen, CommandMenuScreen, InteractiveTUIApp
from ome_zarr_tools.tui.fields import command_description
from ome_zarr_tools.tui.logo import LOGO_MIN_HEIGHT, LOGO_MIN_WIDTH, Logo
from ome_zarr_tools.tui.screens.config_screen import ConfigResultScreen, ConfigScreen
from ome_zarr_tools.tui.screens.metadata_screen import MigrateScreen

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _menu_index(name: str) -> int:
    return sorted(COMMANDS).index(name)


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


async def test_menu_shows_warning_row_for_unrecognized_keys():
    """US2/T015/FR-016: constructed with an unrecognized `OME_ZARR_TOOLS_*` key
    present, the menu shows a warning row below the OptionList naming it."""
    app = InteractiveTUIApp(COMMANDS, unrecognized=["OME_ZARR_TOOLS_TYPO_OPTION"])
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CommandMenuScreen)
        warning = screen.query_one("#unrecognized-keys-warning")
        assert "OME_ZARR_TOOLS_TYPO_OPTION" in str(warning.render())


async def test_menu_has_no_warning_row_when_nothing_unrecognized():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert not screen.query("#unrecognized-keys-warning")


async def test_from_images_form_field_prefilled_from_env_file_default_map():
    """Regression: a `--env-file`-derived default must actually populate the
    generic CommandFormScreen's widget (e.g. from_images's --chunk_size),
    not just silently exist in a mapping nothing reads for display -- an
    Input pre-filled with the option's own built-in default always produces
    an explicit token, so an unrendered override would never apply."""
    default_map = {"from_images": {"chunk_size": "128"}}
    app = InteractiveTUIApp(COMMANDS, default_map=default_map)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("from_images")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, CommandFormScreen)
        chunk_size_input = app.screen.query_one("#field-chunk_size", Input)
        assert chunk_size_input.value == "128"


async def test_migrate_screen_fields_prefilled_from_env_file_default_map():
    """Same regression, for migrate's specialized screen (target_version/
    chunks_per_shard are shared registry variables, also configurable via
    --env-file)."""
    default_map = {"migrate": {"target_version": "0.4", "chunks_per_shard": "4"}}
    app = InteractiveTUIApp(COMMANDS, default_map=default_map)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("migrate")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MigrateScreen)
        assert app.screen._target_input is not None
        assert app.screen._target_input.value == "0.4"
        assert app.screen._shard_input is not None
        assert app.screen._shard_input.value == "4"


async def test_returning_to_menu_reloads_env_file_even_without_using_config_screen(
    tmp_path,
):
    """Regression: the env-file is re-read every time the main menu becomes
    active again, not just after a save through this session's own config
    editor -- covers an external edit (e.g. `config set` run in another
    terminal, or the file edited by hand) made while some other screen was
    on top."""
    env_file = tmp_path / "settings.env"
    env_file.write_text("", encoding="utf-8")

    app = InteractiveTUIApp(COMMANDS, env_file=str(env_file))
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        assert not app.screen.query("#unrecognized-keys-warning")

        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("from_images")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, CommandFormScreen)

        # An edit made entirely outside this TUI session while a different
        # screen is on top (never touches ConfigScreen at all).
        env_file.write_text("OME_ZARR_TOOLS_TYPO_OPTION=1\n", encoding="utf-8")

        await pilot.press("escape")  # back to the menu
        await pilot.pause()

        assert isinstance(app.screen, CommandMenuScreen)
        warning = app.screen.query_one("#unrecognized-keys-warning")
        assert "OME_ZARR_TOOLS_TYPO_OPTION" in str(warning.render())


async def test_saving_active_env_file_in_config_screen_reloads_form_defaults(tmp_path):
    """Regression: editing/saving the *same* env-file this session is running
    with, from the TUI's own config editor, must be reflected immediately in
    subsequently opened form screens' pre-filled defaults -- without
    restarting --tui."""
    env_file = tmp_path / "settings.env"
    env_file.write_text("", encoding="utf-8")

    app = InteractiveTUIApp(COMMANDS, env_file=str(env_file))
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()

        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("config")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ConfigScreen)
        path_input = app.screen.query_one("#field-env_file", Input)
        path_input.focus()
        await pilot.press(*str(env_file))
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = "OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=256"
        editor.focus()  # move focus off the path field before navigating back
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, ConfigResultScreen)
        result_screen = app.screen
        for _ in range(50):
            if result_screen._finished:
                break
            await pilot.pause()

        await pilot.press("escape")  # back to ConfigScreen
        await pilot.pause()
        await pilot.press("escape")  # back to CommandMenuScreen
        await pilot.pause()

        assert isinstance(app.screen, CommandMenuScreen)
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("from_images")
        await pilot.press("enter")
        await pilot.pause()

        chunk_size_input = app.screen.query_one("#field-chunk_size", Input)
        assert chunk_size_input.value == "256"


async def test_fixing_unrecognized_key_in_config_screen_clears_menu_warning(tmp_path):
    """Regression: the menu's unrecognized-key warning must clear immediately
    after the offending key is removed and saved via the config editor,
    without restarting --tui -- not just on the next fresh launch."""
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_TYPO_OPTION=1\n", encoding="utf-8")

    app = InteractiveTUIApp(
        COMMANDS, unrecognized=["OME_ZARR_TOOLS_TYPO_OPTION"], env_file=str(env_file)
    )
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        assert app.screen.query_one("#unrecognized-keys-warning")

        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("config")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ConfigScreen)
        path_input = app.screen.query_one("#field-env_file", Input)
        path_input.focus()
        await pilot.press(*str(env_file))
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        assert "OME_ZARR_TOOLS_TYPO_OPTION" in editor.text
        editor.text = ""  # fix: remove the offending line
        editor.focus()  # move focus off the path field before navigating back
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert isinstance(app.screen, ConfigResultScreen)
        result_screen = app.screen
        for _ in range(50):
            if result_screen._finished:
                break
            await pilot.pause()

        await pilot.press("escape")  # back to ConfigScreen
        await pilot.pause()
        await pilot.press("escape")  # back to CommandMenuScreen
        await pilot.pause()

        assert isinstance(app.screen, CommandMenuScreen)
        assert not app.screen.query("#unrecognized-keys-warning")


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
