import copy
import shutil

import dask.array as da
import numpy as np
import pytest
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.pyramid import NewLevel, commit_new_levels, next_new_paths
from ome_zarr_tools.io.ome_metadata import read_multiscales


def _write_dataset(path, num_levels=2):
    group = zarr.open_group(str(path), mode="w", zarr_format=2)
    datasets = []
    for i in range(num_levels):
        shape = (8 // (2**i), 8 // (2**i), 8 // (2**i))
        arr = group.create_array(str(i), shape=shape, dtype="uint8", chunks=shape)
        arr[:] = np.full(shape, i, dtype="uint8")
        scale = float(2**i)
        datasets.append(
            {"path": str(i), "coordinateTransformations": [{"type": "scale", "scale": [scale] * 3}]}
        )
    group.attrs["multiscales"] = [
        {
            "version": "0.4",
            "name": "Image",
            "axes": [{"name": ax, "type": "space", "unit": "micrometer"} for ax in ("z", "y", "x")],
            "datasets": datasets,
        }
    ]
    return group


def test_next_new_paths_continues_past_max_existing_integer_path():
    existing = [{"path": "0"}, {"path": "1"}]
    assert next_new_paths(existing, 2) == ["2", "3"]


def test_next_new_paths_skips_any_accidental_collision():
    existing = [{"path": "0"}, {"path": "2"}]
    assert next_new_paths(existing, 2) == ["3", "4"]


def test_next_new_paths_empty_datasets_starts_at_zero():
    assert next_new_paths([], 1) == ["0"]


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
