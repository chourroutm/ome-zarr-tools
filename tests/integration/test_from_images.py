import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.from_images import from_images


def test_from_images_success(tmp_path, image_stack_dir):
    runner = CliRunner()
    out = tmp_path / "out.zarr"
    result = runner.invoke(
        from_images,
        [
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            "--voxel_size",
            "1.0",
            "--voxel_size",
            "2.0",
            "--num_downsampling",
            "1",
            "--chunk_size",
            "8",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    group = zarr.open_group(str(out), mode="r")
    assert group["0"].shape == (8, 32, 32)
    assert group["1"].shape == (4, 16, 16)
    scale = group.attrs["multiscales"][0]["datasets"][0]["coordinateTransformations"][0]["scale"]
    assert scale == [1.0, 1.0, 2.0]


def test_from_images_failure_conflicting_inputs(tmp_path, image_stack_dir):
    runner = CliRunner()
    result = runner.invoke(
        from_images,
        [
            "--stack_dir",
            str(image_stack_dir),
            "--vol_file",
            str(image_stack_dir / "slice_000.png"),
            "--voxel_size",
            "1.0",
            str(tmp_path / "out.zarr"),
        ],
    )
    assert result.exit_code != 0
