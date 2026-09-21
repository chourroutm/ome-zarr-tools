from __future__ import annotations

from pathlib import Path

import dask.array as da
import imageio.v3 as iio
import numpy as np
import pytest
import zarr

from ome_zarr_tools.core.pyramid import write_new_pyramid


def _write_ome_zarr(
    path: Path,
    shape: tuple[int, int, int] = (16, 32, 32),
    *,
    zarr_format: int = 2,
    fill: np.ndarray | None = None,
) -> Path:
    data = (
        fill
        if fill is not None
        else np.random.default_rng(0).integers(0, 255, size=shape, dtype="uint8")
    )
    write_new_pyramid(
        path,
        da.from_array(data, chunks=(8, 8, 8)),
        num_downsampling=1,
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=["micrometer", "micrometer", "micrometer"],
        voxel_size=[1.0, 1.0, 1.0],
        chunk_shape=(8, 8, 8),
        shard_shape=None,
        zarr_format=zarr_format,
        image_name="Image",
    )
    return path


@pytest.fixture
def image_stack_dir(tmp_path: Path) -> Path:
    """A directory of 8 natsort-orderable 2D PNG slices (32x32, uint8)."""
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    rng = np.random.default_rng(1)
    for i in range(8):
        slice_ = rng.integers(0, 255, size=(32, 32), dtype="uint8")
        iio.imwrite(stack_dir / f"slice_{i:03d}.png", slice_)
    return stack_dir


@pytest.fixture
def odd_image_stack_dir(tmp_path: Path) -> Path:
    """A directory of 9 natsort-orderable 2D PNG slices (17x17, uint8) --
    every dimension odd/non-power-of-two, unlike ``image_stack_dir``."""
    stack_dir = tmp_path / "odd_stack"
    stack_dir.mkdir()
    rng = np.random.default_rng(4)
    for i in range(9):
        slice_ = rng.integers(0, 255, size=(17, 17), dtype="uint8")
        iio.imwrite(stack_dir / f"slice_{i:03d}.png", slice_)
    return stack_dir


@pytest.fixture
def sample_ome_zarr(tmp_path: Path) -> Path:
    """A valid OME-Zarr 0.4 dataset (Zarr v2 storage), 2 resolution levels, shape (16, 32, 32)."""
    return _write_ome_zarr(tmp_path / "sample.zarr")


@pytest.fixture
def sample_mask_zarr(tmp_path: Path) -> Path:
    """A binary mask OME-Zarr dataset matching ``sample_ome_zarr``'s level-0 shape."""
    mask = (np.random.default_rng(2).random((16, 32, 32)) > 0.5).astype("uint8")
    return _write_ome_zarr(tmp_path / "mask.zarr", shape=(16, 32, 32), fill=mask)


@pytest.fixture
def sample_finer_mask_zarr(tmp_path: Path) -> Path:
    """A binary mask OME-Zarr dataset whose level-0 is 2x *finer* than
    ``sample_ome_zarr``'s -- exercises ``apply_mask``'s downsample-the-mask
    path (``sample_mask_zarr`` matches exactly, so it never needs resampling)."""
    mask = (np.random.default_rng(3).random((32, 64, 64)) > 0.5).astype("uint8")
    return _write_ome_zarr(tmp_path / "finer_mask.zarr", shape=(32, 64, 64), fill=mask)


@pytest.fixture
def legacy_v2_ome_zarr(tmp_path: Path) -> Path:
    """An OME-Zarr 0.4 dataset on Zarr v2 storage, for ``migrate`` tests."""
    return _write_ome_zarr(tmp_path / "legacy.zarr", shape=(8, 16, 16), zarr_format=2)


def open_root_attrs(path: Path) -> dict:
    group = zarr.open_group(str(path), mode="r")
    return dict(group.attrs)
