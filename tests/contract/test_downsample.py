from click.testing import CliRunner

from ome_zarr_tools.commands.downsample import downsample


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
