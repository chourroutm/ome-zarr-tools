from click.testing import CliRunner

from ome_zarr_tools.commands.upsample import upsample


def test_upsample_requires_zarr_path():
    runner = CliRunner()
    result = runner.invoke(upsample, [])
    assert result.exit_code != 0
    assert "Missing argument" in result.output or "ZARR_PATH" in result.output


def test_upsample_help_lists_all_options():
    runner = CliRunner()
    result = runner.invoke(upsample, ["--help"])
    assert result.exit_code == 0
    assert "--num_levels" in result.output
    assert "--smooth" in result.output
    assert "--output" in result.output


def test_upsample_nonexistent_path_is_an_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(upsample, [str(tmp_path / "nope.zarr")])
    assert result.exit_code != 0
