from click.testing import CliRunner

from ome_zarr_tools.commands.config import config


def test_config_round_trip(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()

    result = runner.invoke(config, ["set", str(env_file), "OME_ZARR_TOOLS_TARGET_VERSION=0.5"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(config, ["show", str(env_file)])
    assert result.exit_code == 0, result.output
    assert "OME_ZARR_TOOLS_TARGET_VERSION=0.5" in result.output

    result = runner.invoke(config, ["set", str(env_file), "OME_ZARR_TOOLS_CHUNKS_PER_SHARD=2"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(config, ["reset", str(env_file), "OME_ZARR_TOOLS_TARGET_VERSION"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(config, ["show", str(env_file)])
    assert result.exit_code == 0, result.output
    assert "OME_ZARR_TOOLS_TARGET_VERSION" not in result.output
    assert "OME_ZARR_TOOLS_CHUNKS_PER_SHARD=2" in result.output

    result = runner.invoke(config, ["reset", str(env_file), "--all"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(config, ["show", str(env_file)])
    assert result.exit_code != 0
