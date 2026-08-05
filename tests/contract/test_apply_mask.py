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
