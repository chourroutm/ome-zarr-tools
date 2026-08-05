from pathlib import Path

from click.testing import CliRunner

from ome_zarr_tools.commands.extract import extract


def test_extract_crop_success(tmp_path, sample_ome_zarr):
    runner = CliRunner()
    output = tmp_path / "crop.tif"
    result = runner.invoke(
        extract,
        [
            str(sample_ome_zarr),
            "--corner",
            "0",
            "0",
            "0",
            "--size",
            "4",
            "8",
            "8",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()


def test_extract_full_level_default_output(tmp_path, sample_ome_zarr):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(extract, [str(sample_ome_zarr), "--level", "1"])
        assert result.exit_code == 0, result.output
        import os

        base = os.path.splitext(str(sample_ome_zarr).rstrip("/"))[0]
        expected = Path(f"{base}_level1.ome.tif")
        assert expected.exists()


def test_extract_half_specified_crop_is_failure(tmp_path, sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(extract, [str(sample_ome_zarr), "--corner", "0", "0", "0"])
    assert result.exit_code != 0
