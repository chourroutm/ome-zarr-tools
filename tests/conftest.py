from __future__ import annotations

from pathlib import Path

import imageio.v3 as iio
import numpy as np
import pytest
import zarr
from bioio_ome_zarr.writers import OMEZarrWriter


def _write_ome_zarr(
    path: Path,
    shape: tuple[int, int, int] = (16, 32, 32),
    *,
    zarr_format: int = 2,
    fill: np.ndarray | None = None,
) -> Path:
    level_shapes = [shape, tuple(max(1, s // 2) for s in shape)]
    data = (
        fill
        if fill is not None
        else np.random.default_rng(0).integers(0, 255, size=shape, dtype="uint8")
    )
    import dask.array as da

    writer = OMEZarrWriter(
        str(path),
        level_shapes=level_shapes,
        dtype=data.dtype,
        chunk_shape=(8, 8, 8),
        zarr_format=zarr_format,
        image_name="Image",
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=["micrometer", "micrometer", "micrometer"],
        physical_pixel_size=[1.0, 1.0, 1.0],
    )
    writer.initialize()
    writer.write_full_volume(da.from_array(data, chunks=(8, 8, 8)))
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
def sample_ome_zarr(tmp_path: Path) -> Path:
    """A valid OME-Zarr 0.4 dataset (Zarr v2 storage), 2 resolution levels, shape (16, 32, 32)."""
    return _write_ome_zarr(tmp_path / "sample.zarr")


@pytest.fixture
def sample_mask_zarr(tmp_path: Path) -> Path:
    """A binary mask OME-Zarr dataset matching ``sample_ome_zarr``'s level-0 shape."""
    mask = (np.random.default_rng(2).random((16, 32, 32)) > 0.5).astype("uint8")
    return _write_ome_zarr(tmp_path / "mask.zarr", shape=(16, 32, 32), fill=mask)


@pytest.fixture
def legacy_v2_ome_zarr(tmp_path: Path) -> Path:
    """An OME-Zarr 0.4 dataset on Zarr v2 storage, for ``migrate`` tests."""
    return _write_ome_zarr(tmp_path / "legacy.zarr", shape=(8, 16, 16), zarr_format=2)


def open_root_attrs(path: Path) -> dict:
    group = zarr.open_group(str(path), mode="r")
    return dict(group.attrs)
