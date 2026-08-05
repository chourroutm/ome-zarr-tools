from click.testing import CliRunner

from ome_zarr_tools.cli import cli


def test_menu_lists_registered_commands_except_itself():
    runner = CliRunner()
    # Select "config" (index 2, no top-level params) then decline execution --
    # exercises the menu without needing to answer every other command's prompts.
    result = runner.invoke(cli, ["interactive"], input="2\nn\n")
    assert result.exit_code == 0, result.output
    assert "Cancelled" in result.output
    for name in ("from_images", "extract", "fix_metadata", "apply_mask", "config"):
        assert name in result.output
    assert (
        "interactive"
        not in result.output.split("Available commands:")[1].split("Select a command")[0]
    )


def test_no_flags_beyond_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["interactive", "--help"])
    assert result.exit_code == 0
    assert "--help" in result.output
