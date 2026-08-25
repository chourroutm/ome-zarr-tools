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
    datasets = group.attrs["ome"]["multiscales"][0]["datasets"]  # default --target_version is 0.5
    scale_0, translation_0 = (
        datasets[0]["coordinateTransformations"][0]["scale"],
        datasets[0]["coordinateTransformations"][1]["translation"],
    )
    scale_1, translation_1 = (
        datasets[1]["coordinateTransformations"][0]["scale"],
        datasets[1]["coordinateTransformations"][1]["translation"],
    )
    assert scale_0 == [1.0, 1.0, 2.0]
    assert scale_1 == [2.0, 2.0, 4.0]
    # translation_N = (scale_N - scale_0) / 2 (ngff-spec's documented multi-scale
    # alignment convention for classical-binning downsampling): level 0 is the
    # anchor (translation 0), coarser levels shift to stay aligned to it.
    assert translation_0 == [0.0, 0.0, 0.0]
    assert translation_1 == [0.5, 0.5, 1.0]


def test_from_images_target_version_0_4_writes_legacy_zarr_v2_layout(tmp_path, image_stack_dir):
    runner = CliRunner()
    out = tmp_path / "out.zarr"
    result = runner.invoke(
        from_images,
        [
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            "--chunk_size",
            "8",
            "--target_version",
            "0.4",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    group = zarr.open_group(str(out), mode="r")
    assert group.attrs["multiscales"][0]["version"] == "0.4"
    assert "ome" not in group.attrs


def test_from_images_chunks_per_shard_shards_the_output(tmp_path, image_stack_dir):
    runner = CliRunner()
    out = tmp_path / "out.zarr"
    result = runner.invoke(
        from_images,
        [
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            "--chunk_size",
            "8",
            "--chunks_per_shard",
            "2",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    group = zarr.open_group(str(out), mode="r")
    array = group["0"]
    assert array.chunks == (8, 8, 8)
    assert array.shards == (16, 16, 16)


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
