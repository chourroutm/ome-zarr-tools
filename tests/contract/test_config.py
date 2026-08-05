from click.testing import CliRunner

from ome_zarr_tools.commands.config import config


def test_set_requires_user_or_project(tmp_path):
    runner = CliRunner()
    result = runner.invoke(config, ["set", "key=value"])
    assert result.exit_code != 0


def test_set_rejects_both_user_and_project(tmp_path):
    runner = CliRunner()
    result = runner.invoke(config, ["set", "--user", "--project", str(tmp_path), "key=value"])
    assert result.exit_code != 0
