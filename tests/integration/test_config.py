from click.testing import CliRunner

from ome_zarr_tools.commands.config import config


def test_config_round_trip_project_scope(tmp_path):
    runner = CliRunner()

    result = runner.invoke(config, ["set", "--project", str(tmp_path), "compression=zstd"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(config, ["show", "--project", str(tmp_path)])
    assert result.exit_code == 0
    assert "compression" in result.output
    assert "zstd" in result.output

    result = runner.invoke(config, ["reset", "--project", str(tmp_path), "compression"])
    assert result.exit_code == 0

    result = runner.invoke(config, ["show", "--project", str(tmp_path)])
    assert "zstd" not in result.output


def test_config_set_neither_user_nor_project_is_failure(tmp_path):
    runner = CliRunner()
    result = runner.invoke(config, ["set", "key=value"])
    assert result.exit_code != 0


def test_config_set_both_user_and_project_is_failure(tmp_path):
    runner = CliRunner()
    result = runner.invoke(config, ["set", "--user", "--project", str(tmp_path), "key=value"])
    assert result.exit_code != 0
