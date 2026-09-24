from click.testing import CliRunner

from ome_zarr_tools.commands.apply_mask import apply_mask


def test_missing_required_options_is_an_error(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(apply_mask, ["--volume", str(sample_ome_zarr)])
    assert result.exit_code != 0


def test_threshold_default_is_half(sample_ome_zarr, sample_mask_zarr):
    runner = CliRunner()
    result = runner.invoke(
        apply_mask, ["--volume", str(sample_ome_zarr), "--mask", str(sample_mask_zarr)]
    )
    assert result.exit_code == 0, result.output


def test_temporary_upsample_option_removed(sample_ome_zarr, sample_mask_zarr):
    """FR-013: --temporary_upsample was dead code (mask resampling always
    happens automatically) and has been removed entirely."""
    runner = CliRunner()
    result = runner.invoke(
        apply_mask,
        [
            "--volume",
            str(sample_ome_zarr),
            "--mask",
            str(sample_mask_zarr),
            "--temporary_upsample",
        ],
    )
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()
