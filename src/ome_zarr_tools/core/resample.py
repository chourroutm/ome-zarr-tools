"""Shared array-level resampling primitives, used by ``downsample``/``upsample``
(to build new multiscale levels), ``apply_mask`` (to align a mask's resolution
to its volume's), and ``from_images`` (to build its initial pyramid) alike --
every one of these commands only ever resamples by a factor of 2 per axis.

Both functions stay lazy end to end via ``dask.array.map_blocks``: each dask
block is resampled independently, so the array is never materialized in
memory all at once, only one chunk at a time ever is -- matching this
codebase's own out-of-core-first convention elsewhere (e.g. ``nearest_upsample``
below). ``downsample_func`` needs neighbor context beyond a single block to
antialias perfectly at chunk boundaries, so per-chunk-independent smoothing
trades a small amount of cross-chunk blending precision for staying fully
lazy/out-of-core.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable

import dask.array as da
import numpy as np
import numpy.typing as npt
import skimage.transform


def nearest_upsample(array: da.Array, factor: int = 2) -> da.Array:
    """Exact ``factor``x nearest-neighbor expansion per axis (lazy) -- every
    voxel of the result is one that already existed in ``array`` (never
    interpolated), which is what makes it safe for label/mask data (as well
    as harmless for continuous intensity data).
    """
    upsampled = array
    for axis in range(array.ndim):
        upsampled = da.repeat(upsampled, factor, axis=axis)
    return upsampled


def _downsampled_chunks(
    chunks: tuple[tuple[int, ...], ...], factor: int
) -> tuple[tuple[int, ...], ...]:
    """Per-axis, per-block output sizes after downsampling by ``factor`` --
    matches ``skimage``'s own pyramid downsampling convention (ceiling
    division, verified empirically: a size-17 axis downsamples to 9, not 8),
    computed per dask block rather than once for the whole array so
    non-uniform/boundary blocks (whenever an axis isn't an exact multiple of
    its chunk size) still declare the exact shape ``map_blocks`` will get.
    """
    return tuple(tuple(math.ceil(c / factor) for c in axis) for axis in chunks)


def intensity_downsample(
    data: da.Array,
    factor: int = 2,
    *,
    downsample_func: Callable[..., Iterable[npt.NDArray]] = skimage.transform.pyramid_gaussian,
) -> da.Array:
    """Downsample ``data`` (continuous intensity values) by ``factor`` along
    every axis, lazily -- each dask block is downsampled independently via
    ``downsample_func`` (default: ``skimage.transform.pyramid_gaussian``,
    antialiased). Unlike ``label_downsample``, no per-label-channel
    decomposition is needed: continuous data can be legitimately
    Gaussian-blended across the downsampling window, which is exactly what
    antialiased downsampling should do.
    """

    def _downsample_block(block: npt.NDArray) -> npt.NDArray:
        return list(downsample_func(block, max_layer=1, downscale=factor, preserve_range=True))[
            -1
        ].astype(block.dtype)

    return da.map_blocks(
        _downsample_block, data, dtype=data.dtype, chunks=_downsampled_chunks(data.chunks, factor)
    )


def label_downsample(
    data: da.Array,
    factor: int = 2,
    *,
    smooth: float | None = None,
    downsample_func: Callable[..., Iterable[npt.NDArray]] = skimage.transform.pyramid_gaussian,
) -> da.Array:
    """Downsample ``data`` (label/segmentation values) by ``factor`` along
    every axis, lazily -- each dask block is decomposed into one probability
    channel per distinct label value *present in that block* (a block-local
    subset of the dataset's full label set is enough: every output voxel
    still ends up one of the labels actually present nearby, so the "never
    invent a new value" guarantee holds per block, not just globally),
    downsamples each channel independently with ``downsample_func``, and
    re-snaps every voxel to the label of its highest-probability channel --
    never Gaussian-blending distinct label values together the way
    downsampling the raw integer array directly would (the standard correct
    technique for resampling categorical data; degenerates to
    blur-then-threshold-at-0.5 for a binary mask).
    """

    def _downsample_block(block: npt.NDArray) -> npt.NDArray:
        labels = np.unique(block)
        channels = np.stack(
            [
                list(
                    downsample_func(
                        block == label,
                        max_layer=1,
                        downscale=factor,
                        sigma=smooth,
                        preserve_range=True,
                    )
                )[-1]
                for label in labels
            ]
        )
        return labels[np.argmax(channels, axis=0)].astype(block.dtype)

    return da.map_blocks(
        _downsample_block, data, dtype=data.dtype, chunks=_downsampled_chunks(data.chunks, factor)
    )
