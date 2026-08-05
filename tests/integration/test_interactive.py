import zarr
from click.testing import CliRunner

from ome_zarr_tools.cli import cli


def test_interactive_runs_from_images(tmp_path, image_stack_dir):
    out = tmp_path / "out.zarr"
    runner = CliRunner()
    # Menu selection "5" = from_images (alphabetically last of the 5 US1 commands).
    # Prompts in declaration order: --stack_dir, --stack_pattern, --vol_file,
    # --voxel_size (multiple; blank line to stop), --voxel_size_unit, --num_downsampling,
    # --chunk_size, OUTPUT_ZARR argument, then the final "Run this now?" confirm.
    answers = "\n".join(
        [
            "5",  # select from_images
            str(image_stack_dir),  # --stack_dir
            "",  # --stack_pattern (skip)
            "",  # --vol_file (skip)
            "1.0",  # --voxel_size value 1
            "",  # stop repeating --voxel_size
            "",  # --voxel_size_unit (accept default)
            "",  # --num_downsampling (accept default)
            "",  # --chunk_size (accept default)
            str(out),  # OUTPUT_ZARR argument
            "y",  # Run this now?
            "",
        ]
    )
    result = runner.invoke(cli, ["interactive"], input=answers)
    assert result.exit_code == 0, result.output
    assert "Equivalent command" in result.output

    group = zarr.open_group(str(out), mode="r")
    assert group["0"].shape[0] == 8  # 8 slices in image_stack_dir


def test_interactive_cancel_leaves_no_side_effects(tmp_path, image_stack_dir):
    out = tmp_path / "out.zarr"
    runner = CliRunner()
    answers = "\n".join(
        [
            "5",
            str(image_stack_dir),
            "",
            "",
            "1.0",
            "",
            "",
            "",
            "",
            str(out),
            "n",  # decline final confirmation
            "",
        ]
    )
    result = runner.invoke(cli, ["interactive"], input=answers)
    assert result.exit_code == 0, result.output
    assert "Cancelled" in result.output
    assert not out.exists()
