"""Stack/volume reading shared by ``from_images``."""

from __future__ import annotations

import glob
from pathlib import Path

import dask.array as da


def read_stack(stack_dir: Path | None, stack_pattern: str | None) -> da.Array:
    """Read a directory or glob pattern of 2D slice files into a lazy ``(z, y, x)`` array."""
    pattern = str(Path(stack_dir) / "*") if stack_dir is not None else str(stack_pattern)
    try:
        from dask.array.image import imread

        return imread(pattern)
    except ImportError:
        import imageio.v3 as iio
        from natsort import natsorted

        files = natsorted(glob.glob(pattern))
        slices = [iio.imread(f) for f in files]
        return da.stack([da.from_array(s) for s in slices])


def read_volume(vol_file: Path) -> da.Array:
    """Read a single 3D volume file into a lazy ``(z, y, x)`` array."""
    import imageio.v3 as iio

    return da.from_array(iio.imread(str(vol_file)))
