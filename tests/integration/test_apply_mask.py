import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.apply_mask import apply_mask


def test_apply_mask_success(tmp_path, sample_ome_zarr, sample_mask_zarr):
    before = zarr.open_group(str(sample_ome_zarr), mode="r")["0"][:].sum()

    runner = CliRunner()
    result = runner.invoke(
        apply_mask,
        ["--volume", str(sample_ome_zarr), "--mask", str(sample_mask_zarr), "--threshold", "0.5"],
    )
    assert result.exit_code == 0, result.output

    after = zarr.open_group(str(sample_ome_zarr), mode="r")["0"][:].sum()
    assert after <= before

    backups = list(sample_ome_zarr.parent.glob("sample.zarr_zattrs_backup_*.json"))
    assert len(backups) == 1


def test_apply_mask_no_matching_scale_is_failure(tmp_path, sample_ome_zarr):
    mask_path = tmp_path / "no_match_mask.zarr"
    mask_group = zarr.open_group(str(mask_path), mode="w")
    mask_group.create_array("nomatch", shape=(4, 4, 4), chunks=(4, 4, 4), dtype="uint8")

    runner = CliRunner()
    result = runner.invoke(apply_mask, ["--volume", str(sample_ome_zarr), "--mask", str(mask_path)])
    assert result.exit_code != 0
