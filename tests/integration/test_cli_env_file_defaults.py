from click.testing import CliRunner

from ome_zarr_tools.cli import cli


def test_env_file_supplies_default_when_flag_omitted(tmp_path, image_stack_dir):
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=8\n", encoding="utf-8")
    out = tmp_path / "out.zarr"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "--env-file",
            str(env_file),
            "from_images",
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    import zarr

    group = zarr.open_group(str(out), mode="r")
    assert group["0"].chunks == (8, 8, 8)


def test_explicit_flag_overrides_env_file_default(tmp_path, image_stack_dir):
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=8\n", encoding="utf-8")
    out = tmp_path / "out.zarr"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "--env-file",
            str(env_file),
            "from_images",
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            "--chunk_size",
            "4",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    import zarr

    group = zarr.open_group(str(out), mode="r")
    assert group["0"].chunks == (4, 4, 4)


def test_omitting_env_file_behaves_as_today(tmp_path, image_stack_dir):
    out = tmp_path / "out.zarr"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "from_images",
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    import zarr

    group = zarr.open_group(str(out), mode="r")
    assert group["0"].chunks == (64, 64, 64)  # from_images's built-in default


def test_invalid_value_produces_clear_error_naming_option(tmp_path, image_stack_dir):
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=notanumber\n", encoding="utf-8")
    out = tmp_path / "out.zarr"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "--env-file",
            str(env_file),
            "from_images",
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            str(out),
        ],
    )

    assert result.exit_code != 0
    assert "--chunk_size" in result.output
    assert "Traceback" not in result.output


def test_unrecognized_key_prints_nonblocking_warning_and_command_still_runs(
    tmp_path, image_stack_dir
):
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_TYPO_OPTION=1\n", encoding="utf-8")
    out = tmp_path / "out.zarr"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "--env-file",
            str(env_file),
            "from_images",
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "OME_ZARR_TOOLS_TYPO_OPTION" in result.output


def test_shared_target_version_applies_to_from_images_and_migrate(
    tmp_path, image_stack_dir, legacy_v2_ome_zarr
):
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_TARGET_VERSION=0.5\n", encoding="utf-8")
    runner = CliRunner()

    import zarr

    out = tmp_path / "out.zarr"
    result = runner.invoke(
        cli,
        [
            "--env-file",
            str(env_file),
            "from_images",
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    # 0.5 layout, even though --target_version was never passed explicitly.
    assert "ome" in zarr.open_group(str(out), mode="r").attrs

    result = runner.invoke(
        cli, ["--env-file", str(env_file), "migrate", str(legacy_v2_ome_zarr)], input="y\n"
    )
    assert result.exit_code == 0, result.output
    assert "ome" in zarr.open_group(str(legacy_v2_ome_zarr), mode="r").attrs


def test_downsample_scoped_num_levels_does_not_leak_to_upsample(tmp_path, sample_ome_zarr):
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS=3\n", encoding="utf-8")
    runner = CliRunner()

    import zarr

    def _dataset_count() -> int:
        attrs = zarr.open_group(str(sample_ome_zarr), mode="r").attrs
        return len(attrs["multiscales"][0]["datasets"])

    before = _dataset_count()
    result = runner.invoke(cli, ["--env-file", str(env_file), "upsample", str(sample_ome_zarr)])
    assert result.exit_code == 0, result.output
    # upsample's own built-in default (1) is used, not downsample's scoped 3.
    assert _dataset_count() - before == 1


def test_duplicate_key_prints_warning_and_last_occurrence_applies(tmp_path, image_stack_dir):
    env_file = tmp_path / "settings.env"
    env_file.write_text(
        "OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=8\nOME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=16\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.zarr"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "--env-file",
            str(env_file),
            "from_images",
            "--stack_dir",
            str(image_stack_dir),
            "--voxel_size",
            "1.0",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE" in result.output  # duplicate-key warning
    import zarr

    group = zarr.open_group(str(out), mode="r")
    assert group["0"].chunks == (16, 16, 16)  # last occurrence wins
