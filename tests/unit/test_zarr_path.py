import click
import pytest

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.zarr_path import ZarrPathParamType, is_remote_path, validate_output_path


@pytest.mark.parametrize(
    "value",
    [
        "gs://bucket/dataset.ome.zarr",
        "gcs://bucket/dataset.ome.zarr",
        "s3://bucket/dataset.ome.zarr",
        "http://example.com/dataset.ome.zarr",
        "https://example.com/dataset.ome.zarr",
    ],
)
def test_is_remote_path_recognizes_common_schemes(value):
    assert is_remote_path(value) is True


def test_is_remote_path_rejects_local_paths(tmp_path):
    assert is_remote_path(str(tmp_path / "dataset.ome.zarr")) is False
    assert is_remote_path("relative/dataset.ome.zarr") is False


def test_zarr_path_param_type_accepts_remote_url_without_local_existence_check():
    param_type = ZarrPathParamType(exists=True)
    result = param_type.convert("gs://bucket/does-not-exist-locally.ome.zarr", None, None)
    assert result == "gs://bucket/does-not-exist-locally.ome.zarr"


def test_zarr_path_param_type_still_enforces_local_existence(tmp_path):
    param_type = ZarrPathParamType(exists=True)
    with pytest.raises(click.BadParameter):
        param_type.convert(str(tmp_path / "nope.zarr"), None, None)


def test_zarr_path_param_type_accepts_existing_local_path(tmp_path):
    real_dir = tmp_path / "dataset.ome.zarr"
    real_dir.mkdir()
    param_type = ZarrPathParamType(exists=True)
    assert param_type.convert(str(real_dir), None, None) == str(real_dir)


def test_validate_output_path_none_is_a_noop():
    validate_output_path(None)  # must not raise


def test_validate_output_path_nonexistent_is_a_noop(tmp_path):
    validate_output_path(tmp_path / "does-not-exist-yet.zarr")  # must not raise


def test_validate_output_path_rejects_existing_path(tmp_path):
    existing = tmp_path / "already-here.zarr"
    existing.mkdir()
    with pytest.raises(CliError, match="already exists"):
        validate_output_path(existing)
