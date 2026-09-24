from click.testing import CliRunner

from ome_zarr_tools.commands.config import config
from ome_zarr_tools.core.env_file import read_env_file


def test_set_creates_file_if_absent(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()

    result = runner.invoke(
        config, ["set", str(env_file), "OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.7"]
    )

    assert result.exit_code == 0, result.output
    values, warnings = read_env_file(env_file)
    assert values == {"OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD": "0.7"}
    assert warnings == []


def test_set_on_existing_key_updates_in_place_no_duplicate(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()

    runner.invoke(config, ["set", str(env_file), "FOO=1"])
    result = runner.invoke(config, ["set", str(env_file), "FOO=2"])
    assert result.exit_code == 0, result.output

    values, warnings = read_env_file(env_file)
    assert values == {"FOO": "2"}
    assert warnings == []  # no duplicate-key warning: updated in place, not appended


def test_set_invalid_key_exits_nonzero_and_writes_nothing(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()

    result = runner.invoke(config, ["set", str(env_file), "1BAD=x"])

    assert result.exit_code != 0
    assert not env_file.exists()


def test_set_invalid_key_leaves_existing_file_unchanged(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()
    runner.invoke(config, ["set", str(env_file), "FOO=1"])

    result = runner.invoke(config, ["set", str(env_file), "FOO=2", "1BAD=x"])

    assert result.exit_code != 0
    values, _ = read_env_file(env_file)
    assert values == {"FOO": "1"}


def test_set_reports_preexisting_unrecognized_key_as_error(tmp_path):
    env_file = tmp_path / "settings.env"
    env_file.write_text("OME_ZARR_TOOLS_TYPO_OPTION=1\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(config, ["set", str(env_file), "FOO=1"])

    assert result.exit_code == 0, result.output
    assert "OME_ZARR_TOOLS_TYPO_OPTION" in result.output
    values, _ = read_env_file(env_file)
    assert values["FOO"] == "1"  # the new pair is still written


def test_set_reports_preexisting_duplicate_key_as_warning(tmp_path):
    env_file = tmp_path / "settings.env"
    env_file.write_text("FOO=1\nFOO=2\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(config, ["set", str(env_file), "BAR=1"])

    assert result.exit_code == 0, result.output
    assert "FOO" in result.output
    values, _ = read_env_file(env_file)
    assert values["BAR"] == "1"  # the new pair is still written


def test_show_flags_only_the_unrecognized_prefixed_key(tmp_path):
    env_file = tmp_path / "settings.env"
    env_file.write_text(
        "OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.5\n"
        "OME_ZARR_TOOLS_TYPO_OPTION=1\n"
        "AWS_ACCESS_KEY_ID=fake\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(config, ["show", str(env_file)])

    assert result.exit_code == 0, result.output
    assert "OME_ZARR_TOOLS_TYPO_OPTION" in result.output
    # AWS_ACCESS_KEY_ID must never be reported as unrecognized -- only OME_ZARR_TOOLS_*
    # prefixed keys are eligible for that flag.
    error_lines = [line for line in result.output.splitlines() if "unrecognized" in line.lower()]
    assert error_lines and all("AWS_ACCESS_KEY_ID" not in line for line in error_lines)


def test_show_duplicate_key_warns_and_displays_last_value(tmp_path):
    env_file = tmp_path / "settings.env"
    env_file.write_text(
        "OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.1\nOME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.9\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(config, ["show", str(env_file)])

    assert result.exit_code == 0, result.output
    assert "OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD" in result.output
    assert "0.9" in result.output


def test_reset_one_key_removes_it_no_op_if_absent(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()
    runner.invoke(config, ["set", str(env_file), "FOO=1", "BAR=2"])

    result = runner.invoke(config, ["reset", str(env_file), "FOO"])
    assert result.exit_code == 0, result.output
    values, _ = read_env_file(env_file)
    assert values == {"BAR": "2"}

    result = runner.invoke(config, ["reset", str(env_file), "NOT_PRESENT"])
    assert result.exit_code == 0, result.output


def test_reset_all_deletes_file(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()
    runner.invoke(config, ["set", str(env_file), "FOO=1"])

    result = runner.invoke(config, ["reset", str(env_file), "--all"])
    assert result.exit_code == 0, result.output
    assert not env_file.exists()


def test_show_and_reset_on_nonexistent_file_exit_nonzero(tmp_path):
    env_file = tmp_path / "does_not_exist.env"
    runner = CliRunner()

    result = runner.invoke(config, ["show", str(env_file)])
    assert result.exit_code != 0

    result = runner.invoke(config, ["reset", str(env_file), "FOO"])
    assert result.exit_code != 0


def test_reset_neither_keys_nor_all_is_an_error(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()
    runner.invoke(config, ["set", str(env_file), "FOO=1"])

    result = runner.invoke(config, ["reset", str(env_file)])

    assert result.exit_code != 0
    values, _ = read_env_file(env_file)
    assert values == {"FOO": "1"}  # nothing removed


def test_reset_both_keys_and_all_is_an_error(tmp_path):
    env_file = tmp_path / "settings.env"
    runner = CliRunner()
    runner.invoke(config, ["set", str(env_file), "FOO=1"])

    result = runner.invoke(config, ["reset", str(env_file), "--all", "FOO"])

    assert result.exit_code != 0
    values, _ = read_env_file(env_file)
    assert values == {"FOO": "1"}  # nothing removed
