import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.fix_metadata import fix_metadata


def test_fix_metadata_success_writes_valid_metadata_and_backup(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(
        fix_metadata,
        [str(sample_ome_zarr)],
        input="MyImage\nmicrometer\n1.0 1.0 1.0\nz y x\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "successfully written" in result.output.lower()

    backups = list(sample_ome_zarr.parent.glob("sample.zarr_zattrs_backup_*.json"))
    assert len(backups) == 1

    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    assert group.attrs["multiscales"][0]["name"] == "MyImage"


def test_fix_metadata_failure_restores_backup_on_invalid_metadata(sample_ome_zarr):
    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    original_multiscales = group.attrs["multiscales"]

    runner = CliRunner()
    result = runner.invoke(
        fix_metadata,
        [str(sample_ome_zarr)],
        input="MyImage\nmicrometer\n1.0 1.0 1.0\nz z x\ny\n",
    )
    assert result.exit_code != 0

    restored = zarr.open_group(str(sample_ome_zarr), mode="r").attrs["multiscales"]
    assert restored == original_multiscales
