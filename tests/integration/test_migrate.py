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
