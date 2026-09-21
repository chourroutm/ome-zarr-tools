import copy
import shutil

import dask
import dask.array as da
import numpy as np
import pytest
import skimage.transform
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.pyramid import (
    NewLevel,
    commit_new_levels,
    next_new_paths,
    write_new_pyramid,
)
from ome_zarr_tools.io.ome_metadata import read_multiscales, validate


def _write_dataset(path, num_levels=2, *, zarr_format=2):
    group = zarr.open_group(str(path), mode="w", zarr_format=zarr_format)
    axes = [{"name": ax, "type": "space", "unit": "micrometer"} for ax in ("z", "y", "x")]
    datasets = []
    for i in range(num_levels):
        shape = (8 // (2**i), 8 // (2**i), 8 // (2**i))
        create_kwargs = {"dimension_names": ("z", "y", "x")} if zarr_format == 3 else {}
        arr = group.create_array(str(i), shape=shape, dtype="uint8", chunks=shape, **create_kwargs)
        arr[:] = np.full(shape, i, dtype="uint8")
        scale = float(2**i)
        datasets.append(
            {"path": str(i), "coordinateTransformations": [{"type": "scale", "scale": [scale] * 3}]}
        )
    if zarr_format == 3:
        multiscales = [{"name": "Image", "axes": axes, "datasets": datasets}]
        group.attrs["ome"] = {"version": "0.5", "multiscales": multiscales}
    else:
        multiscales = [{"version": "0.4", "name": "Image", "axes": axes, "datasets": datasets}]
        group.attrs["multiscales"] = multiscales
    return group


def test_next_new_paths_continues_past_max_existing_integer_path():
    existing = [{"path": "0"}, {"path": "1"}]
    assert next_new_paths(existing, 2) == ["2", "3"]


def test_next_new_paths_skips_any_accidental_collision():
    existing = [{"path": "0"}, {"path": "2"}]
    assert next_new_paths(existing, 2) == ["3", "4"]


def test_next_new_paths_empty_datasets_starts_at_zero():
    assert next_new_paths([], 1) == ["0"]


def test_next_new_paths_skips_stray_array_not_in_datasets_metadata(tmp_path):
    """Regression: a leftover array on disk from an interrupted prior run (or
    any other array not recorded in `datasets`) must still be avoided --
    otherwise the coming `group.create_array()` fails with "an array already
    exists at path ...". `existing_datasets` alone can't see it; only the
    actual group listing can.
    """
    group = zarr.open_group(str(tmp_path / "data.zarr"), mode="w", zarr_format=2)
    group.create_array("0", shape=(4, 4, 4), dtype="uint8", chunks=(4, 4, 4))
    group.create_array("1", shape=(2, 2, 2), dtype="uint8", chunks=(2, 2, 2))  # stray, unrecorded
    existing_datasets = [{"path": "0"}]  # "1" is missing from here

    assert next_new_paths(existing_datasets, 1, group=group) == ["2"]


def test_commit_new_levels_self_heals_past_a_path_that_actually_already_exists(tmp_path):
    """Regression: a group opened with (auto-detected) consolidated metadata
    reports membership from a cached listing that a just-created array isn't
    reflected in until the group is explicitly re-consolidated -- so even
    next_new_paths()'s own group-based collision check can hand back a path
    that collides for real. `create_array()` itself always sees the live
    store, so `commit_new_levels()` must recover from that collision instead
    of failing outright: claim the next integer path and keep going.
    """
    path = tmp_path / "data.zarr"
    group = _write_dataset(path)
    # A stray array at "2" -- exactly what next_new_paths() would hand out next --
    # present on disk but, unlike a real regression, deliberately not routed
    # through next_new_paths() here so the test doesn't depend on reproducing
    # the consolidated-metadata staleness mechanism itself.
    group.create_array("2", shape=(1, 1, 1), dtype="uint8", chunks=(1, 1, 1))

    new_array = da.from_array(np.full((2, 2, 2), 9, dtype="uint8"), chunks=(2, 2, 2))
    new_level = NewLevel(path="2", array=new_array, chunks=(2, 2, 2), scale=[4.0, 4.0, 4.0])

    commit_new_levels(path, group, [new_level], position="append")

    group = zarr.open_group(str(path), mode="r")
    multiscales = read_multiscales(group)
    paths = [d["path"] for d in multiscales[0]["datasets"]]
    assert paths == ["0", "1", "3"]  # "2" was claimed, so the new level became "3"
    assert group["3"][:].sum() == 9 * 8


def test_commit_new_levels_append_writes_array_and_extends_datasets(tmp_path):
    path = tmp_path / "data.zarr"
    group = _write_dataset(path)

    new_array = da.from_array(np.full((2, 2, 2), 9, dtype="uint8"), chunks=(2, 2, 2))
    new_level = NewLevel(
        path="2",
        array=new_array,
        chunks=(2, 2, 2),
        scale=[4.0, 4.0, 4.0],
    )

    commit_new_levels(path, group, [new_level], position="append")

    group = zarr.open_group(str(path), mode="r")
    assert group["2"][:].sum() == 9 * 8
    multiscales = read_multiscales(group)
    paths = [d["path"] for d in multiscales[0]["datasets"]]
    assert paths == ["0", "1", "2"]


def test_commit_new_levels_prepend_puts_new_entry_first(tmp_path):
    path = tmp_path / "data.zarr"
    group = _write_dataset(path)

    new_array = da.from_array(np.full((16, 16, 16), 7, dtype="uint8"), chunks=(8, 8, 8))
    new_level = NewLevel(
        path="2",
        array=new_array,
        chunks=(8, 8, 8),
        scale=[0.5, 0.5, 0.5],
    )

    commit_new_levels(path, group, [new_level], position="prepend")

    group = zarr.open_group(str(path), mode="r")
    multiscales = read_multiscales(group)
    datasets = multiscales[0]["datasets"]
    paths = [d["path"] for d in datasets]
    assert paths == ["2", "0", "1"]
    # existing levels' own data is untouched
    assert group["0"][:].sum() == 0
    assert group["1"][:].sum() == 4 * 4 * 4
    # translations are recomputed relative to the *new* datasets[0] ("2"): the
    # new finest level is always anchored at zero, and the previously-finest
    # level ("0") -- now second -- gets a nonzero translation it didn't have
    # before, since it's no longer the reference level.
    translations = {
        d["path"]: next(
            t["translation"] for t in d["coordinateTransformations"] if t["type"] == "translation"
        )
        for d in datasets
    }
    assert translations["2"] == [0.0, 0.0, 0.0]
    assert translations["0"] == [0.25, 0.25, 0.25]


def test_commit_new_levels_zarr_v3_dataset_passes_validation(tmp_path):
    """Regression: on a Zarr v3 (OME-NGFF 0.5) dataset, the new array must get
    ``dimension_names`` set (zarr v3's per-axis-name array metadata) -- without
    it, ``ome_zarr_models``' own validation rejects the dataset ("has no
    dimension_names metadata"), which previously made every 0.5 downsample/
    upsample fail regardless of input.
    """
    path = tmp_path / "data.zarr"
    group = _write_dataset(path, zarr_format=3)

    new_array = da.from_array(np.full((2, 2, 2), 9, dtype="uint8"), chunks=(2, 2, 2))
    new_level = NewLevel(path="2", array=new_array, chunks=(2, 2, 2), scale=[4.0, 4.0, 4.0])

    commit_new_levels(path, group, [new_level], position="append")

    group = zarr.open_group(str(path), mode="r")
    is_valid, error = validate(group)
    assert is_valid, error
    assert group["2"].metadata.dimension_names == ("z", "y", "x")


def test_commit_new_levels_restores_attrs_and_removes_arrays_on_validation_failure(tmp_path):
    path = tmp_path / "data.zarr"
    group = _write_dataset(path)
    # deepcopy: dict(group.attrs) is shallow, and commit_new_levels() mutates the
    # same nested `datasets` list objects in place before it fails -- a shallow
    # "before" snapshot would silently drift along with that mutation.
    attrs_before = copy.deepcopy(dict(group.attrs))

    # A coordinateTransformations shaped for a 2D dataset, deliberately incompatible
    # with this 3-axis dataset's own axes -- triggers validate() to fail.
    new_array = da.from_array(np.zeros((2, 2), dtype="uint8"), chunks=(2, 2))
    bad_level = NewLevel(
        path="2",
        array=new_array,
        chunks=(2, 2),
        scale=[4.0, 4.0],
    )

    with pytest.raises(CliError):
        commit_new_levels(path, group, [bad_level], position="append")

    group = zarr.open_group(str(path), mode="r")
    assert dict(group.attrs) == attrs_before
    assert "2" not in list(group.array_keys())


def test_commit_new_levels_output_mode_copies_dataset_leaves_original_untouched(tmp_path):
    source = tmp_path / "data.zarr"
    _write_dataset(source)
    output = tmp_path / "out.zarr"
    before_files = sorted(f.name for f in source.iterdir())

    new_array = da.from_array(np.full((2, 2, 2), 5, dtype="uint8"), chunks=(2, 2, 2))
    new_level = NewLevel(
        path="2",
        array=new_array,
        chunks=(2, 2, 2),
        scale=[4.0, 4.0, 4.0],
    )

    shutil.copytree(source, output)
    output_group = zarr.open_group(str(output), mode="r+")
    commit_new_levels(output, output_group, [new_level], position="append")

    assert sorted(f.name for f in source.iterdir()) == before_files
    result_group = zarr.open_group(str(output), mode="r")
    assert "2" in list(result_group.array_keys())


def test_write_new_pyramid_scale_metadata_matches_actual_shape_for_odd_dimensions(tmp_path):
    """Regression: scale must be derived from the level's real (lazily-declared)
    output shape, never an independently precomputed one -- for an odd-sized
    dimension, skimage's own ceiling-division convention (17 -> 9) diverges
    from a naive floor-division precompute (17 -> 8), which would otherwise
    silently record a scale value that doesn't correspond to what's on disk.
    """
    path = tmp_path / "odd.zarr"
    arr = da.from_array(np.zeros((17, 17, 17), dtype="uint8"), chunks=(8, 8, 8))

    write_new_pyramid(
        path,
        arr,
        1,
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=["micrometer"] * 3,
        voxel_size=[2.0, 2.0, 2.0],
        chunk_shape=(8, 8, 8),
        shard_shape=None,
        zarr_format=2,
        image_name="Image",
    )

    group = zarr.open_group(str(path), mode="r")
    assert group["1"].shape == (9, 9, 9)
    scale = group.attrs["multiscales"][0]["datasets"][1]["coordinateTransformations"][0]["scale"]
    assert scale == pytest.approx([2.0 * 17 / 9] * 3)


def test_write_new_pyramid_issues_one_combined_store_call_not_one_per_level(tmp_path):
    """Regression: separate da.store() calls per level would recompute every
    shared upstream step once per level -- one combined call must read the
    source exactly once regardless of how many levels are built from it.
    """
    path = tmp_path / "batched.zarr"
    data = np.zeros((16, 16, 16), dtype="uint8")
    calls = {"n": 0}

    def _load() -> np.ndarray:
        calls["n"] += 1
        return data

    arr = da.from_delayed(dask.delayed(_load)(), shape=data.shape, dtype=data.dtype).rechunk(
        (8, 8, 8)
    )

    write_new_pyramid(
        path,
        arr,
        2,
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=["micrometer"] * 3,
        voxel_size=[1.0, 1.0, 1.0],
        chunk_shape=(8, 8, 8),
        shard_shape=None,
        zarr_format=2,
        image_name="Image",
    )

    assert calls["n"] == 1


def test_write_new_pyramid_never_processes_more_than_one_chunk_at_a_time(tmp_path):
    """FR-007/SC-003: memory use per processing step must be bounded
    independent of total dataset size. Rather than an OS-level memory limit
    (platform-inconsistent, risks killing the test process outright instead
    of failing cleanly), this instruments every array actually handed to the
    downsampling function and asserts each one is exactly one chunk's worth
    of data -- never the whole (much larger) array -- proving the mechanism
    that makes boundedness true by construction.
    """
    path = tmp_path / "large.zarr"
    chunk_shape = (4, 4, 4)
    # 8x more voxels along each axis than a single chunk (512x more total)
    # -- if any call ever saw the whole array, its shape would be nowhere
    # near chunk_shape. Kept modest (8**3 = 512 chunks) so the test itself
    # stays fast: this is about proving per-call boundedness, not actually
    # exercising a large dataset end to end.
    arr = da.zeros((32, 32, 32), chunks=chunk_shape, dtype="uint8")

    seen_shapes: list[tuple[int, ...]] = []

    def _tracking_downsample_func(block, **kwargs):
        seen_shapes.append(block.shape)
        return skimage.transform.pyramid_gaussian(block, **kwargs)

    write_new_pyramid(
        path,
        arr,
        1,
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=["micrometer"] * 3,
        voxel_size=[1.0, 1.0, 1.0],
        chunk_shape=chunk_shape,
        shard_shape=None,
        zarr_format=2,
        image_name="Image",
        downsample_func=_tracking_downsample_func,
    )

    assert seen_shapes  # the downsample path was actually exercised
    # dask internally probes the block function once with an empty
    # (all-zero-dim) array to infer output dtype/meta -- harmless, not a
    # real materialization -- every *real* call must still be exactly one
    # chunk's worth of data, never anywhere close to the full 32x32x32 array.
    real_shapes = [shape for shape in seen_shapes if 0 not in shape]
    assert real_shapes
    assert all(shape == chunk_shape for shape in real_shapes)
