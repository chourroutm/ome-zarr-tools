from click.testing import CliRunner

from ome_zarr_tools.commands.extract import extract


def test_corner_without_size_is_an_error(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(extract, [str(sample_ome_zarr), "--corner", "0", "0", "0"])
    assert result.exit_code != 0


def test_size_without_corner_is_an_error(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(extract, [str(sample_ome_zarr), "--size", "4", "4", "4"])
    assert result.exit_code != 0


def test_unknown_level_is_an_error(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(extract, [str(sample_ome_zarr), "--level", "9"])
    assert result.exit_code != 0
