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


def test_interactive_prompt_flow_unchanged_regression(tmp_path):
    """Locks in the exact menu/prompt text for `interactive` (no flag).

    Added alongside 002-textual-tui-interactive's --tui flag and the
    _confirm_and_run extraction, to guard FR-001/SC-001: the prompt-based
    flow must not change in any observable way.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["interactive"], input="2\nn\n")
    assert result.exit_code == 0, result.output
    assert (
        "Available commands:\n"
        "  1. apply_mask\n"
        "  2. config\n"
        "  3. extract\n"
        "  4. fix_metadata\n"
        "  5. from_images\n"
        "  6. inspect\n"
        "  7. migrate\n"
    ) in result.output
    assert "Select a command:" in result.output
    assert "\n--- config ---\n" in result.output
    assert "\nEquivalent command:\n  ome-zarr-tools config\n" in result.output
    assert "Run this now? [Y/n]:" in result.output
    assert "Cancelled. No changes were made." in result.output


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
