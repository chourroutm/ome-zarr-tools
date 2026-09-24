import json

from click.testing import CliRunner

from ome_zarr_tools.commands.inspect import inspect


def test_format_option_removed(sample_ome_zarr):
    """FR-012: --format/output_format no longer exists -- --json (a flag) replaces it."""
    runner = CliRunner()
    result = runner.invoke(inspect, [str(sample_ome_zarr), "--format", "json"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_nonexistent_path_is_an_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(inspect, [str(tmp_path / "nope.zarr")])
    assert result.exit_code != 0


def test_json_output_is_parseable(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(inspect, [str(sample_ome_zarr), "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert "levels" in report and "total_stored_bytes" in report
