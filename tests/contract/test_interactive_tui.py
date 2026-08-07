from click.testing import CliRunner

from ome_zarr_tools.cli import cli
from ome_zarr_tools.commands.from_images import from_images
from ome_zarr_tools.commands.inspect import inspect
from ome_zarr_tools.tui.app import CommandFormScreen, InteractiveTUIApp
from ome_zarr_tools.tui.fields import build_autocomplete, build_field_widget


def test_command_form_has_no_button_and_has_footer_shortcuts():
    action_names = {binding.action for binding in CommandFormScreen.BINDINGS}
    assert action_names == {
        "run",
        "copy",
        "copy_and_exit",
        "toggle_log",
        "back",
        "cancel",
        "restore_defaults",  # spec 004 FR-027
    }
    # No Button widget is used to run a command (FR-005) -- no "submit"-style
    # binding/id anywhere in the class definition. Spec 004's Browse button
    # (US4) lives on the `PathField` widget, not the screen class itself.
    assert not hasattr(CommandFormScreen, "on_button_pressed")


def test_path_field_gets_autocomplete_non_path_field_does_not():
    # from_images.stack_dir is a click.Path option -> autocomplete attached
    stack_dir_param = next(p for p in from_images.params if p.name == "stack_dir")
    widget = build_field_widget(stack_dir_param)
    assert build_autocomplete(stack_dir_param, widget) is not None

    # inspect.output_format is a click.Choice option -> no autocomplete
    format_param = next(p for p in inspect.params if p.name == "output_format")
    widget = build_field_widget(format_param)
    assert build_autocomplete(format_param, widget) is None


def test_help_lists_tui_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["interactive", "--help"])
    assert result.exit_code == 0
    assert "--tui" in result.output


def test_tui_without_interactive_terminal_fails_clearly():
    runner = CliRunner()
    result = runner.invoke(cli, ["interactive", "--tui"])
    assert result.exit_code != 0
    assert "interactive terminal" in result.output
    assert "Traceback" not in result.output


def test_tui_menu_matches_prompt_based_menu():
    commands = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}
    app = InteractiveTUIApp(commands)
    assert set(app.commands) == set(commands)
    assert "interactive" not in app.commands
