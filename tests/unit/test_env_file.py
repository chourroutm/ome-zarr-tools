import pytest

from ome_zarr_tools.core.env_file import is_valid_env_key, read_env_file, write_env_file
from ome_zarr_tools.core.errors import CliError


def test_read_write_round_trip(tmp_path):
    path = tmp_path / "settings.env"
    write_env_file(path, {"FOO": "1", "BAR": "baz"})

    values, warnings = read_env_file(path)

    assert values == {"FOO": "1", "BAR": "baz"}
    assert warnings == []


def test_read_skips_blank_and_comment_lines(tmp_path):
    path = tmp_path / "settings.env"
    path.write_text("\n# a comment\nFOO=1\n   \n# another\nBAR=2\n", encoding="utf-8")

    values, warnings = read_env_file(path)

    assert values == {"FOO": "1", "BAR": "2"}
    assert warnings == []


def test_read_missing_file_raises_clean_error(tmp_path):
    path = tmp_path / "does_not_exist.env"

    with pytest.raises(CliError) as exc_info:
        read_env_file(path)

    assert str(path) in str(exc_info.value)


def test_read_malformed_line_raises_with_path_and_line_number(tmp_path):
    path = tmp_path / "settings.env"
    path.write_text("FOO=1\nNOT_A_PAIR\nBAR=2\n", encoding="utf-8")

    with pytest.raises(CliError) as exc_info:
        read_env_file(path)

    message = str(exc_info.value)
    assert str(path) in message
    assert "2" in message  # 1-indexed line number of the malformed line


def test_read_duplicate_key_last_wins_with_warning(tmp_path):
    path = tmp_path / "settings.env"
    path.write_text("FOO=1\nFOO=2\n", encoding="utf-8")

    values, warnings = read_env_file(path)

    assert values == {"FOO": "2"}
    assert len(warnings) == 1
    assert "FOO" in warnings[0]


def test_is_valid_env_key_accepts_identifier_pattern():
    assert is_valid_env_key("FOO") is True
    assert is_valid_env_key("_FOO_1") is True
    assert is_valid_env_key("OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE") is True


@pytest.mark.parametrize("key", ["1BAD", "BAD-KEY", "BAD KEY", "", "BAD.KEY"])
def test_is_valid_env_key_rejects_non_identifiers(key):
    assert is_valid_env_key(key) is False


def test_write_creates_parent_and_one_line_per_entry(tmp_path):
    path = tmp_path / "nested" / "settings.env"
    write_env_file(path, {"FOO": "1", "BAR": "2"})

    assert path.read_text(encoding="utf-8") == "FOO=1\nBAR=2\n"
