import numpy as np
import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.migrate import migrate


def test_migrate_success_and_idempotent(legacy_v2_ome_zarr):
    before = zarr.open_group(str(legacy_v2_ome_zarr), mode="r")["0"][:]
    checksum_before = np.asarray(before).sum()

    runner = CliRunner()
    result = runner.invoke(
        migrate, [str(legacy_v2_ome_zarr), "--target_version", "0.5"], input="y\n"
    )
    assert result.exit_code == 0, result.output
    assert "Migrated" in result.output

    backups = list(legacy_v2_ome_zarr.parent.glob("legacy.zarr_zattrs_backup_*.json"))
    assert len(backups) == 1

    group = zarr.open_group(str(legacy_v2_ome_zarr), mode="r")
    assert group.attrs["ome"]["version"] == "0.5"

    dataset_path = group.attrs["ome"]["multiscales"][0]["datasets"][0]["path"]
    migrated_arr = group[dataset_path][:]
    assert np.asarray(migrated_arr).sum() == checksum_before

    # Re-running with the same target should now be a no-op.
    result2 = runner.invoke(migrate, [str(legacy_v2_ome_zarr), "--target_version", "0.5"])
    assert result2.exit_code == 0, result2.output
    assert "already at version" in result2.output


def test_migrate_with_chunks_per_shard_writes_sharded_zarr_v3(legacy_v2_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(
        migrate,
        [str(legacy_v2_ome_zarr), "--target_version", "0.5", "--chunks_per_shard", "2"],
        input="y\n",
    )
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(legacy_v2_ome_zarr), mode="r")
    assert group.metadata.zarr_format == 3
    dataset_path = group.attrs["ome"]["multiscales"][0]["datasets"][0]["path"]
    array = group[dataset_path]
    assert array.shards is not None


def test_migrate_chunks_per_shard_rejected_for_pre_0_5_target(legacy_v2_ome_zarr):
    """Sharding is a Zarr v3 (OME-NGFF 0.5+) concept -- Zarr v2 (0.4) has none, so
    this combination must be rejected before any zarr I/O."""
    before = dict(zarr.open_group(str(legacy_v2_ome_zarr), mode="r").attrs)

    runner = CliRunner()
    result = runner.invoke(
        migrate,
        [str(legacy_v2_ome_zarr), "--target_version", "0.4", "--chunks_per_shard", "2"],
    )
    assert result.exit_code != 0
    assert "chunks_per_shard" in result.output
    assert "0.5" in result.output

    after = dict(zarr.open_group(str(legacy_v2_ome_zarr), mode="r").attrs)
    assert before == after  # rejected before touching the dataset -- no backup file either
    assert not list(legacy_v2_ome_zarr.parent.glob("legacy.zarr_zattrs_backup_*.json"))


def test_migrate_with_output_writes_new_location_leaves_original_untouched(
    tmp_path, legacy_v2_ome_zarr
):
    before = dict(zarr.open_group(str(legacy_v2_ome_zarr), mode="r").attrs)
    output = tmp_path / "migrated.zarr"

    runner = CliRunner()
    result = runner.invoke(
        migrate,
        [str(legacy_v2_ome_zarr), "--target_version", "0.5", "--output", str(output)],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert str(output) in result.output

    after = dict(zarr.open_group(str(legacy_v2_ome_zarr), mode="r").attrs)
    assert before == after  # original completely untouched
    assert not list(legacy_v2_ome_zarr.parent.glob("legacy.zarr_zattrs_backup_*.json"))

    output_group = zarr.open_group(str(output), mode="r")
    assert output_group.attrs["ome"]["version"] == "0.5"


def test_migrate_with_output_rejects_existing_path(tmp_path, legacy_v2_ome_zarr):
    output = tmp_path / "already_here.zarr"
    output.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate, [str(legacy_v2_ome_zarr), "--target_version", "0.5", "--output", str(output)]
    )
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_migrate_with_output_and_same_version_still_writes_a_copy(tmp_path, legacy_v2_ome_zarr):
    """Unlike in-place migration, --output to a same-version target is not a
    no-op -- e.g. re-sharding without a version bump is a legitimate use."""
    output = tmp_path / "copy.zarr"

    runner = CliRunner()
    result = runner.invoke(
        migrate,
        [str(legacy_v2_ome_zarr), "--target_version", "0.4", "--output", str(output)],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert "already at version" not in result.output
    assert output.exists()


def test_migrate_declined_confirmation_leaves_dataset_untouched(legacy_v2_ome_zarr):
    before = dict(zarr.open_group(str(legacy_v2_ome_zarr), mode="r").attrs)

    runner = CliRunner()
    result = runner.invoke(
        migrate, [str(legacy_v2_ome_zarr), "--target_version", "0.5"], input="n\n"
    )
    assert result.exit_code == 0
    assert "Aborted" in result.output

    after = dict(zarr.open_group(str(legacy_v2_ome_zarr), mode="r").attrs)
    assert before == after
