import dask.array as da
import numpy as np
import zarr
from click.testing import CliRunner

from ome_zarr_tools.commands.upsample import upsample
from ome_zarr_tools.core.pyramid import write_new_pyramid


def _level_paths(group) -> list[str]:
    return [d["path"] for d in group.attrs["multiscales"][0]["datasets"]]


def test_upsample_default_adds_one_finer_level_in_place(sample_mask_zarr):
    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr)])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_mask_zarr), mode="r")
    paths = _level_paths(group)
    assert len(paths) == 3
    new_path = paths[0]
    # sample_mask_zarr's existing finest level (path "0") is shape (16, 32, 32)
    assert group[new_path].shape == (32, 64, 64)


def test_upsample_never_introduces_a_value_not_in_the_source(sample_mask_zarr):
    group_before = zarr.open_group(str(sample_mask_zarr), mode="r")
    source_values = set(np.unique(group_before["0"][:]).tolist())

    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr)])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_mask_zarr), mode="r")
    new_path = _level_paths(group)[0]
    new_values = set(np.unique(group[new_path][:]).tolist())
    assert new_values <= source_values


def test_upsample_num_levels_adds_that_many_progressively_finer_levels(sample_mask_zarr):
    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr), "--num_levels", "2"])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_mask_zarr), mode="r")
    paths = _level_paths(group)
    assert len(paths) == 4  # 2 existing + 2 new
    shapes = [group[p].shape for p in paths]
    assert shapes == [(64, 128, 128), (32, 64, 64), (16, 32, 32), (8, 16, 16)]


def test_upsample_output_leaves_original_untouched(tmp_path, sample_mask_zarr):
    before_files = sorted(f.name for f in sample_mask_zarr.rglob("*") if f.is_file())
    output = tmp_path / "upsampled.zarr"

    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr), "--output", str(output)])
    assert result.exit_code == 0, result.output

    after_files = sorted(f.name for f in sample_mask_zarr.rglob("*") if f.is_file())
    assert after_files == before_files
    output_group = zarr.open_group(str(output), mode="r")
    assert len(_level_paths(output_group)) == 3


def test_upsample_reorders_new_finest_level_to_datasets_zero(sample_mask_zarr):
    group_before = zarr.open_group(str(sample_mask_zarr), mode="r")
    existing_level_0 = group_before["0"][:]
    existing_level_1 = group_before["1"][:]

    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr)])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_mask_zarr), mode="r")
    paths = _level_paths(group)
    new_path = paths[0]
    assert new_path not in ("0", "1")  # freshly chosen, not reusing an existing path
    assert paths[1:] == ["0", "1"]
    # existing levels' own data is untouched
    assert np.array_equal(group["0"][:], existing_level_0)
    assert np.array_equal(group["1"][:], existing_level_1)


def test_upsample_smooth_keeps_only_original_label_values(sample_mask_zarr):
    group_before = zarr.open_group(str(sample_mask_zarr), mode="r")
    source_values = set(np.unique(group_before["0"][:]).tolist())

    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr), "--smooth", "1.0"])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_mask_zarr), mode="r")
    new_path = _level_paths(group)[0]
    new_values = set(np.unique(group[new_path][:]).tolist())
    assert new_values <= source_values


def test_upsample_without_smooth_is_exact_nearest_neighbor_repeat(sample_mask_zarr):
    group_before = zarr.open_group(str(sample_mask_zarr), mode="r")
    source = group_before["0"][:]

    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr)])
    assert result.exit_code == 0, result.output

    group = zarr.open_group(str(sample_mask_zarr), mode="r")
    new_path = _level_paths(group)[0]
    upsampled = group[new_path][:]
    # Each source voxel becomes an exact 2x2x2 block of itself.
    expected = source.repeat(2, axis=0).repeat(2, axis=1).repeat(2, axis=2)
    assert np.array_equal(upsampled, expected)


def test_upsample_output_rejects_existing_path(tmp_path, sample_mask_zarr):
    output = tmp_path / "already_here.zarr"
    output.mkdir()

    runner = CliRunner()
    result = runner.invoke(upsample, [str(sample_mask_zarr), "--output", str(output)])
    assert result.exit_code != 0
    assert "already exists" in result.output


def _write_v3_dataset(path, data, shard_shape):
    write_new_pyramid(
        path,
        da.from_array(data),
        num_downsampling=0,
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=["micrometer"] * 3,
        voxel_size=[1.0, 1.0, 1.0],
        chunk_shape=(8, 8, 8),
        shard_shape=shard_shape,
        zarr_format=3,
        image_name="Image",
    )


def test_upsample_keeps_the_source_sharding_and_matches_unsharded_output(tmp_path):
    data = (np.random.default_rng(6).random((16, 20, 20)) > 0.5).astype("uint8")
    sharded, unsharded = tmp_path / "sharded.zarr", tmp_path / "unsharded.zarr"
    _write_v3_dataset(sharded, data, (16, 16, 16))
    _write_v3_dataset(unsharded, data, None)

    runner = CliRunner()
    for path in (sharded, unsharded):
        result = runner.invoke(upsample, [str(path), "--num_levels", "2"])
        assert result.exit_code == 0, result.output

    sharded_group = zarr.open_group(str(sharded), mode="r")
    unsharded_group = zarr.open_group(str(unsharded), mode="r")
    new_paths = [d["path"] for d in sharded_group.attrs["ome"]["multiscales"][0]["datasets"][:2]]
    for path in new_paths:
        assert sharded_group[path].shards == (16, 16, 16)
        assert sharded_group[path].chunks == (8, 8, 8)
        assert unsharded_group[path].shards is None
        np.testing.assert_array_equal(sharded_group[path][:], unsharded_group[path][:])
    assert sharded_group[new_paths[0]].shape == (64, 80, 80)
