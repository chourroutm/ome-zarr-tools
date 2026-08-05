import hashlib
import json

from click.testing import CliRunner

from ome_zarr_tools.commands.inspect import inspect


def _checksum_dir(path) -> str:
    digest = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            digest.update(f.name.encode())
            digest.update(f.read_bytes())
    return digest.hexdigest()


def test_inspect_reports_correct_shapes_and_is_read_only(sample_ome_zarr):
    before_checksum = _checksum_dir(sample_ome_zarr)

    runner = CliRunner()
    result = runner.invoke(inspect, [str(sample_ome_zarr), "--format", "json"])
    assert result.exit_code == 0, result.output

    report = json.loads(result.output)
    levels = {level["path"]: level for level in report["levels"]}
    assert levels["0"]["shape"] == [16, 32, 32]
    assert levels["1"]["shape"] == [8, 16, 16]
    assert levels["0"]["chunk_shape"] == [8, 8, 8]
    assert levels["0"]["shard_shape"] is None
    assert report["total_logical_bytes"] == sum(lvl["logical_bytes"] for lvl in levels.values())
    assert report["metadata_valid"] is True

    after_checksum = _checksum_dir(sample_ome_zarr)
    assert before_checksum == after_checksum


def test_inspect_text_output_lists_levels(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(inspect, [str(sample_ome_zarr)])
    assert result.exit_code == 0, result.output
    assert "Level 0:" in result.output
    assert "Level 1:" in result.output
    assert "Total stored size" in result.output
