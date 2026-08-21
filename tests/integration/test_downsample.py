import hashlib

import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.downsample import downsample


def _checksum_dir(path) -> str:
    digest = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            digest.update(f.name.encode())
            digest.update(f.read_bytes())
    return digest.hexdigest()


def _level_paths(group) -> list[str]:
    return [d["path"] for d in group.attrs["multiscales"][0]["datasets"]]


def test_downsample_default_adds_one_coarser_level_in_place(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(downsample, [str(sample_ome_zarr)])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    paths = _level_paths(group)
    assert len(paths) == 3
    new_path = paths[-1]
    # sample_ome_zarr's coarsest existing level (path "1") is shape (8, 16, 16)
    assert group[new_path].shape == (4, 8, 8)


def test_downsample_num_levels_adds_that_many_progressively_coarser_levels(sample_ome_zarr):
    runner = CliRunner()
    result = runner.invoke(downsample, [str(sample_ome_zarr), "--num_levels", "3"])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_ome_zarr), mode="r")
    paths = _level_paths(group)
    assert len(paths) == 5  # 2 existing + 3 new
    shapes = [group[p].shape for p in paths]
    assert shapes == [(16, 32, 32), (8, 16, 16), (4, 8, 8), (2, 4, 4), (1, 2, 2)]


def test_downsample_output_leaves_original_untouched(tmp_path, sample_ome_zarr):
    before_checksum = _checksum_dir(sample_ome_zarr)
    output = tmp_path / "downsampled.zarr"

    runner = CliRunner()
    result = runner.invoke(downsample, [str(sample_ome_zarr), "--output", str(output)])
    assert result.exit_code == 0, result.output

    assert _checksum_dir(sample_ome_zarr) == before_checksum
    output_group = zarr.open_group(str(output), mode="r")
    assert len(_level_paths(output_group)) == 3


def test_downsample_output_rejects_existing_path(tmp_path, sample_ome_zarr):
    output = tmp_path / "already_here.zarr"
    output.mkdir()

    runner = CliRunner()
    result = runner.invoke(downsample, [str(sample_ome_zarr), "--output", str(output)])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_downsample_rejects_dataset_with_no_multiscales_metadata(tmp_path):
    broken = tmp_path / "broken.zarr"
    zarr.open_group(str(broken), mode="w")  # a bare group, no multiscales at all

    runner = CliRunner()
    result = runner.invoke(downsample, [str(broken)])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def _existing_level_contents(zarr_path) -> dict[str, bytes]:
    contents = {}
    for level in ("0", "1"):
        for f in (zarr_path / level).rglob("*"):
            if f.is_file():
                contents[str(f.relative_to(zarr_path))] = f.read_bytes()
    return contents


def test_downsample_in_place_leaves_existing_levels_byte_for_byte_unchanged(sample_ome_zarr):
    before = _existing_level_contents(sample_ome_zarr)

    runner = CliRunner()
    result = runner.invoke(downsample, [str(sample_ome_zarr)])
    assert result.exit_code == 0, result.output

    assert _existing_level_contents(sample_ome_zarr) == before
