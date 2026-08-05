from click.testing import CliRunner

from ome_zarr_tools.commands.migrate import migrate


def test_already_current_is_a_noop(legacy_v2_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(migrate, [str(legacy_v2_ome_zarr), "--target_version", "0.4"])
    assert result.exit_code == 0, result.output
    assert "already at version" in result.output


def test_nonexistent_path_is_an_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(migrate, [str(tmp_path / "nope.zarr")])
    assert result.exit_code != 0
