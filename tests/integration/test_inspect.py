import hashlib
import json

import zarr
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


def test_inspect_reports_a_clean_error_for_a_dataset_with_no_zarr_metadata(tmp_path):
    """No .zattrs/.zgroup/zarr.json anywhere (incomplete download) must not leak a traceback."""
    broken = tmp_path / "broken.ome.zarr"
    (broken / "0" / "c").mkdir(parents=True)

    runner = CliRunner()
    result = runner.invoke(inspect, [str(broken)])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "No Zarr group found" in result.output


def test_inspect_degrades_gracefully_when_stored_bytes_is_unavailable(monkeypatch, sample_ome_zarr):
    """A store that denies listing (e.g. an anonymous-read-only remote bucket) must not crash."""

    def _raise_permission_error(self):
        raise PermissionError("listing denied")

    monkeypatch.setattr(zarr.Array, "nbytes_stored", _raise_permission_error)

    runner = CliRunner()
    result = runner.invoke(inspect, [str(sample_ome_zarr), "--format", "json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["total_stored_bytes"] is None
    assert all(level["stored_bytes"] is None for level in report["levels"])

    text_result = runner.invoke(inspect, [str(sample_ome_zarr)])
    assert text_result.exit_code == 0, text_result.output
    assert "unknown (store denied listing)" in text_result.output
