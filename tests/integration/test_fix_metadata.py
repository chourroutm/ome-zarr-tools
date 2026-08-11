import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.fix_metadata import compute_default_prompt_values, fix_metadata


def test_compute_default_prompt_values_with_no_existing_metadata():
    defaults = compute_default_prompt_values(None)
    assert defaults.name == "Image"
    assert defaults.spatial_unit == "micrometer"
    assert defaults.voxel_size == (1.0, 1.0, 1.0)
    assert defaults.axis_names == ["z", "y", "x"]
    assert defaults.dataset_paths == ["0"]


def test_compute_default_prompt_values_matches_existing_metadata(sample_ome_zarr):
    from ome_zarr_tools.io.ome_metadata import read_multiscales

    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    multiscales = read_multiscales(group)

    defaults = compute_default_prompt_values(multiscales)
    assert defaults.name == multiscales[0]["name"]
    assert defaults.dataset_paths == [d["path"] for d in multiscales[0]["datasets"]]


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
