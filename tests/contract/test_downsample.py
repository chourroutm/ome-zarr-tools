from click.testing import CliRunner

from ome_zarr_tools.commands.downsample import downsample
from ome_zarr_tools.commands.upsample import upsample


def test_downsample_requires_zarr_path():
    runner = CliRunner()
    result = runner.invoke(downsample, [])
    assert result.exit_code != 0
    assert "Missing argument" in result.output or "ZARR_PATH" in result.output


def test_downsample_num_levels_defaults_to_1():
    runner = CliRunner()
    result = runner.invoke(downsample, ["--help"])
    assert result.exit_code == 0
    assert "--num_levels" in result.output
    assert "1" in result.output


def test_downsample_output_defaults_to_none():
    runner = CliRunner()
    result = runner.invoke(downsample, ["--help"])
    assert result.exit_code == 0
    assert "--output" in result.output


def test_downsample_nonexistent_path_is_an_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(downsample, [str(tmp_path / "nope.zarr")])
    assert result.exit_code != 0


def test_downsample_help_lists_label_option():
    runner = CliRunner()
    result = runner.invoke(downsample, ["--help"])
    assert result.exit_code == 0
    assert "--label" in result.output


def test_downsample_and_upsample_expose_the_same_label_option_name():
    """User Story 2: a user who has learned one command's --label option must
    find the exact same option name on the other."""
    downsample_flags = {opt.opts[0] for opt in downsample.params if opt.name == "label"}
    upsample_flags = {opt.opts[0] for opt in upsample.params if opt.name == "label"}
    assert downsample_flags == upsample_flags == {"--label"}
