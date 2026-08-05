from click.testing import CliRunner

from ome_zarr_tools.commands.from_images import from_images


def test_requires_exactly_one_input_source(tmp_path, image_stack_dir):
    runner = CliRunner()
    result = runner.invoke(
        from_images,
        [
            "--stack_dir",
            str(image_stack_dir),
            "--stack_pattern",
            str(image_stack_dir / "*.png"),
            "--voxel_size",
            "1.0",
            str(tmp_path / "out.zarr"),
        ],
    )
    assert result.exit_code != 0
    assert "exactly one" in result.output.lower()


def test_no_input_source_is_an_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(from_images, ["--voxel_size", "1.0", str(tmp_path / "out.zarr")])
    assert result.exit_code != 0


def test_voxel_size_arity_validated(tmp_path, image_stack_dir):
    runner = CliRunner()
    result = runner.invoke(
        from_images,
        [
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            "--voxel_size",
            "2.0",
            str(tmp_path / "out.zarr"),
        ],
    )
    assert result.exit_code != 0
    assert "1 or 3" in result.output
