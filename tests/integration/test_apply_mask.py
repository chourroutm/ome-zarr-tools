import hashlib

import numpy as np
import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.apply_mask import apply_mask


def _checksum_dir(path) -> str:
    digest = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            digest.update(f.name.encode())
            digest.update(f.read_bytes())
    return digest.hexdigest()


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


def test_apply_mask_output_leaves_original_untouched(tmp_path, sample_ome_zarr, sample_mask_zarr):
    before_checksum = _checksum_dir(sample_ome_zarr)
    output = tmp_path / "masked.zarr"

    runner = CliRunner()
    result = runner.invoke(
        apply_mask,
        [
            "--volume",
            str(sample_ome_zarr),
            "--mask",
            str(sample_mask_zarr),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output

    assert _checksum_dir(sample_ome_zarr) == before_checksum
    before = zarr.open_group(str(sample_ome_zarr), mode="r")["0"][:].sum()
    after = zarr.open_group(str(output), mode="r")["0"][:].sum()
    assert after <= before


def test_apply_mask_downsampled_mask_never_introduces_a_value_absent_from_the_source(
    sample_ome_zarr, sample_finer_mask_zarr
):
    """The mask needs downsampling to match whichever scale ``apply_mask``
    picks as ``matching_scale`` (both fixtures share keys "0" and "1", and
    zarr's own key iteration order -- not this test -- decides which one
    that is) -- the result must still be exactly binary (0/1) multiplication,
    never a blended/invented mask value (the mask is always treated as label
    data). If the mask were ever fractional, some voxel would end up neither
    zeroed out nor equal to its original value. Checks both levels (whichever
    one actually got masked, plus the untouched one trivially satisfies the
    same invariant) and confirms at least one level really was modified, so
    the test can't pass vacuously against a dataset nothing touched.
    """
    before = {
        level: zarr.open_group(str(sample_ome_zarr), mode="r")[level][:] for level in ("0", "1")
    }

    runner = CliRunner()
    result = runner.invoke(
        apply_mask, ["--volume", str(sample_ome_zarr), "--mask", str(sample_finer_mask_zarr)]
    )
    assert result.exit_code == 0, result.output

    after = {
        level: zarr.open_group(str(sample_ome_zarr), mode="r")[level][:] for level in ("0", "1")
    }
    for level in ("0", "1"):
        assert np.all((after[level] == 0) | (after[level] == before[level]))
    assert any(not np.array_equal(after[level], before[level]) for level in ("0", "1"))


def test_apply_mask_output_rejects_existing_path(tmp_path, sample_ome_zarr, sample_mask_zarr):
    output = tmp_path / "already_here.zarr"
    output.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        apply_mask,
        [
            "--volume",
            str(sample_ome_zarr),
            "--mask",
            str(sample_mask_zarr),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code != 0
    assert "already exists" in result.output
