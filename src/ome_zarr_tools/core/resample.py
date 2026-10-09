"""Shared array-level resampling primitives, used by ``downsample``/``upsample``
(to build new multiscale levels), ``apply_mask`` (to align a mask's resolution
to its volume's), and ``from_images`` (to build its initial pyramid) alike --
every one of these commands only ever resamples by a factor of 2 per axis.

Both functions stay lazy end to end via ``dask.array``: no whole level is ever
materialized in memory, only one chunk (plus a small halo) at a time ever is --
matching this codebase's own out-of-core-first convention elsewhere (e.g.
``nearest_upsample`` below).

For the default ``downsample_func`` (``skimage.transform.pyramid_gaussian``),
both functions use ``dask.array.map_overlap`` to give each chunk a small halo
of real neighboring data before Gaussian-smoothing it, so antialiasing blends
correctly across chunk boundaries -- unlike smoothing each chunk in isolation
(which is measurably wrong right at the seams). Decimation (picking every
``factor``-th smoothed sample) is a plain fixed-stride slice, not
``skimage.transform.resize``: resize's coordinate mapping depends on each
block's own local ``in_size/out_size`` ratio, which silently diverges from
the intended global factor whenever a chunk's size isn't itself a multiple of
``factor`` (an ordinary, not-tiny remainder chunk, e.g. from an
odd-length axis) -- verified empirically to corrupt output near such
boundaries. Fixed-stride decimation has no such dependency, as long as every
chunk except the last one along an axis is itself a multiple of ``factor``
(``_validate_chunk_alignment`` enforces this explicitly on the default path;
dask/zarr chunking for this codebase's own array construction never produces
more than one irregular chunk per axis, and it's always the last one).

A caller-supplied non-default ``downsample_func`` can't be safely
reimplemented this way, so it takes a separate, unchanged fallback path
(today's original chunk-independent ``map_blocks`` behavior, no halo, no
chunk-alignment restriction).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable

import dask.array as da
import numpy as np
import numpy.typing as npt
import scipy.ndimage
import skimage.transform

from ome_zarr_tools.core.errors import CliError


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
    Also exactly matches fixed-stride decimation's real output length
    (``len(range(0, n, factor)) == math.ceil(n / factor)``, verified for a
    wide sweep of ``n``/``factor`` values).
    """
    return tuple(tuple(math.ceil(c / factor) for c in axis) for axis in chunks)


def _default_sigma(factor: int) -> float:
    """``skimage.transform.pyramid_reduce``'s own default antialiasing sigma."""
    return 2 * factor / 6.0


def _gaussian_depth(sigma: float) -> int:
    """Halo radius needed for ``scipy.ndimage.gaussian_filter``'s default
    ``truncate=4.0`` kernel to see all the real neighboring data it would use
    on an unchunked array."""
    return int(4.0 * sigma + 0.5)


def _validate_chunk_alignment(chunks: tuple[tuple[int, ...], ...], factor: int) -> None:
    """Every chunk except the last along each axis must be a multiple of
    ``factor`` -- required for fixed-stride decimation to stay globally
    grid-aligned across chunk boundaries. A violation means the chunk size
    feeding this (a CLI ``--chunk_size``, or an existing zarr array's own
    chunk shape) isn't a multiple of ``factor``; raise clearly rather than
    silently producing a wrong-shaped/corrupted result.
    """
    for axis_chunks in chunks:
        if any(c % factor != 0 for c in axis_chunks[:-1]):
            raise CliError(
                f"Chunk sizes must be a multiple of {factor} along every axis "
                f"(except possibly the last, trailing one) for downsampling; "
                f"got {chunks}."
            )


def _merge_undersized_trailing_chunk(data: da.Array, depth: int) -> da.Array:
    """If the last chunk along an axis is smaller than ``depth``, merge it
    entirely into its predecessor (repeating if still too small). Never
    redistributes a non-last chunk's size -- unlike
    ``da.overlap.ensure_minimum_chunksize``, which can turn a
    factor-aligned non-last chunk into a non-aligned one, breaking fixed-
    stride decimation's grid-alignment precondition. A no-op when every
    chunk already meets ``depth``.
    """
    new_chunks = []
    for axis_chunks in data.chunks:
        merged = list(axis_chunks)
        while len(merged) > 1 and merged[-1] < depth:
            merged[-2] += merged[-1]
            merged.pop()
        new_chunks.append(tuple(merged))
    adjusted = tuple(new_chunks)
    return data.rechunk(adjusted) if adjusted != data.chunks else data


def _per_axis_depth(chunks: tuple[tuple[int, ...], ...], depth: int) -> dict[int, int]:
    """No halo needed along an axis with only one chunk -- a single block
    already sees that whole axis's true extent directly, so there's no seam
    to fix and no minimum-chunksize concern either (this matters for
    repeated downsampling, e.g. ``downsample --num_levels N``: each level's
    output can shrink down to a single chunk per axis well before ``N``
    iterations are done, and there's no predecessor chunk left for
    ``_merge_undersized_trailing_chunk`` to merge into at that point)."""
    return {axis: (depth if len(axis_chunks) > 1 else 0) for axis, axis_chunks in enumerate(chunks)}


def _to_float(block: npt.NDArray) -> npt.NDArray:
    """Matches ``skimage.util.convert_to_float(..., preserve_range=True)``'s
    real behavior: floating dtypes pass through unchanged, everything else
    becomes ``float64``."""
    return block if np.issubdtype(block.dtype, np.floating) else block.astype(np.float64)


def intensity_downsample(
    data: da.Array,
    factor: int = 2,
    *,
    downsample_func: Callable[..., Iterable[npt.NDArray]] = skimage.transform.pyramid_gaussian,
) -> da.Array:
    """Downsample ``data`` (continuous intensity values) by ``factor`` along
    every axis, lazily. Unlike ``label_downsample``, no per-label-channel
    decomposition is needed: continuous data can be legitimately
    Gaussian-blended across the downsampling window, which is exactly what
    antialiased downsampling should do.

    For the default ``downsample_func``, uses a halo-aware two-stage dask
    pipeline (see module docstring) so antialiasing blends correctly across
    chunk boundaries, and requires every non-last chunk along each axis to be
    a multiple of ``factor`` (``CliError`` otherwise). A non-default
    ``downsample_func`` takes an unchanged, chunk-independent fallback path
    with no halo and no chunk-size restriction -- an arbitrary caller-supplied
    function can't be safely reimplemented as the direct scipy/skimage calls
    the default path relies on.
    """
    if downsample_func is not skimage.transform.pyramid_gaussian:

        def _downsample_block(block: npt.NDArray) -> npt.NDArray:
            return list(downsample_func(block, max_layer=1, downscale=factor, preserve_range=True))[
                -1
            ].astype(block.dtype)

        return da.map_blocks(
            _downsample_block,
            data,
            dtype=data.dtype,
            chunks=_downsampled_chunks(data.chunks, factor),
        )

    _validate_chunk_alignment(data.chunks, factor)
    data = _merge_undersized_trailing_chunk(data, _gaussian_depth(_default_sigma(factor)))

    sigma = _default_sigma(factor)
    depth = _gaussian_depth(sigma)
    input_dtype = data.dtype

    def _smooth_block(block: npt.NDArray) -> npt.NDArray:
        return scipy.ndimage.gaussian_filter(
            _to_float(block), sigma=sigma, mode="reflect", truncate=4.0
        )

    smoothed = data.map_overlap(
        _smooth_block,
        depth=_per_axis_depth(data.chunks, depth),
        boundary="reflect",
        trim=True,
        allow_rechunk=False,
        dtype=_to_float(np.zeros(1, dtype=input_dtype)).dtype,
    )

    def _decimate_block(block: npt.NDArray) -> npt.NDArray:
        decimate = tuple(slice(0, None, factor) for _ in range(block.ndim))
        return block[decimate].astype(input_dtype)

    return da.map_blocks(
        _decimate_block,
        smoothed,
        dtype=input_dtype,
        chunks=_downsampled_chunks(smoothed.chunks, factor),
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
    channel per distinct label value *present in that block (plus its halo,
    on the default path)*, each channel is smoothed independently, and every
    output voxel is re-snapped to the label of its highest-probability
    channel -- never Gaussian-blending distinct label values together the
    way downsampling the raw integer array directly would (the standard
    correct technique for resampling categorical data; degenerates to
    blur-then-threshold-at-0.5 for a binary mask). "Never invents a value"
    holds by construction: every value a block can ever see -- padded or
    not -- traces back to a real source value.

    For the default ``downsample_func``, each block is given a halo of real
    neighboring label data (via ``dask.array.map_overlap``) before channel
    decomposition, so a block's local label set and smoothing both see
    correct cross-chunk context -- no global label-inventory pass needed,
    since decomposition/smoothing/decimation/argmax all stay inside one
    per-block function. Requires every non-last chunk along each axis to be
    a multiple of ``factor`` (``CliError`` otherwise), same as
    ``intensity_downsample``. A non-default ``downsample_func`` takes an
    unchanged, chunk-independent fallback path with no halo and no
    chunk-size restriction.
    """
    if downsample_func is not skimage.transform.pyramid_gaussian:

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
            _downsample_block,
            data,
            dtype=data.dtype,
            chunks=_downsampled_chunks(data.chunks, factor),
        )

    sigma = smooth if smooth is not None else _default_sigma(factor)
    depth = _gaussian_depth(sigma)

    _validate_chunk_alignment(data.chunks, factor)
    data = _merge_undersized_trailing_chunk(data, depth)
    axis_depth = _per_axis_depth(data.chunks, depth)
    out_chunks = _downsampled_chunks(data.chunks, factor)

    def _downsample_block_with_halo(padded_block: npt.NDArray) -> npt.NDArray:
        crop = tuple(
            slice(axis_depth[axis], -axis_depth[axis]) if axis_depth[axis] > 0 else slice(None)
            for axis in range(padded_block.ndim)
        )
        decimate = tuple(slice(0, None, factor) for _ in range(padded_block.ndim))
        labels = np.unique(padded_block)
        channels = []
        for label in labels:
            channel = (padded_block == label).astype(np.float64)
            smoothed = scipy.ndimage.gaussian_filter(
                channel, sigma=sigma, mode="reflect", truncate=4.0
            )
            channels.append(smoothed[crop][decimate])
        stacked = np.stack(channels, axis=0)
        return labels[np.argmax(stacked, axis=0)].astype(padded_block.dtype)

    return da.map_overlap(
        _downsample_block_with_halo,
        data,
        depth=axis_depth,
        boundary="reflect",
        trim=False,
        chunks=out_chunks,
        dtype=data.dtype,
        allow_rechunk=False,
    )


def label_smooth(data: da.Array, sigma: float) -> da.Array:
    """Soften ``data``'s label boundaries without changing its shape, lazily:
    the same per-block channel decomposition as ``label_downsample`` (one
    Gaussian-smoothed probability channel per label present in the block
    plus its halo, re-snapped to the highest-probability label), minus the
    decimation. Never invents a value, and matches smoothing the whole array
    at once exactly: a label absent from a block's halo has zero probability
    on that block's interior, so it could never have won there anyway.
    """
    depth = _gaussian_depth(sigma)
    data = _merge_undersized_trailing_chunk(data, depth)
    axis_depth = _per_axis_depth(data.chunks, depth)

    def _smooth_block_with_halo(padded_block: npt.NDArray) -> npt.NDArray:
        crop = tuple(
            slice(axis_depth[axis], -axis_depth[axis]) if axis_depth[axis] > 0 else slice(None)
            for axis in range(padded_block.ndim)
        )
        labels = np.unique(padded_block)
        channels = np.stack(
            [
                scipy.ndimage.gaussian_filter(
                    (padded_block == label).astype(np.float64),
                    sigma=sigma,
                    mode="reflect",
                    truncate=4.0,
                )[crop]
                for label in labels
            ]
        )
        return labels[np.argmax(channels, axis=0)].astype(padded_block.dtype)

    return da.map_overlap(
        _smooth_block_with_halo,
        data,
        depth=axis_depth,
        boundary="reflect",
        trim=False,
        chunks=data.chunks,
        dtype=data.dtype,
        allow_rechunk=False,
    )
