from __future__ import annotations

import shutil
from pathlib import Path

import click
import dask.array as da
import numpy as np
import scipy.ndimage
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.pyramid import NewLevel, commit_new_levels, next_new_paths
from ome_zarr_tools.core.zarr_path import ZarrPathParamType, validate_output_path
from ome_zarr_tools.io.ome_metadata import read_multiscales


def _smooth_labels(level: np.ndarray, sigma: float) -> np.ndarray:
    """Soften ``level``'s label boundaries, re-snapping every voxel to the
    nearest *original* discrete label value (FR-010) -- never leaving a
    blurred/non-discrete value. Decomposes into one channel per distinct
    label, smooths each independently, then takes the per-voxel argmax --
    the standard correct technique for smoothing categorical data (naively
    blurring the raw label array would treat label values as ordinal, which
    is wrong for anything but a binary mask; see research.md).
    """
    labels = np.unique(level)
    channels = np.stack(
        [scipy.ndimage.gaussian_filter((level == label).astype(float), sigma) for label in labels]
    )
    return labels[np.argmax(channels, axis=0)].astype(level.dtype)


def _upsample_once(array: da.Array) -> da.Array:
    """Exact 2x nearest-neighbor expansion per spatial axis -- every voxel of
    the result is one that already existed in ``array`` (never interpolated),
    which is what makes discreteness (FR-009) true by construction."""
    upsampled = array
    for axis in range(array.ndim):
        upsampled = da.repeat(upsampled, 2, axis=axis)
    return upsampled


def _build_new_finer_levels(
    zarr_path: Path, num_levels: int, smooth: float | None
) -> list[NewLevel]:
    """Read ``zarr_path``'s existing finest level and build ``num_levels`` new,
    progressively finer levels above it. Each new level upsamples the one
    before it (not always the original finest), so ``num_levels`` levels form
    a proper chain, each 2x finer than its immediate predecessor.
    """
    group = zarr.open_group(str(zarr_path), mode="r")
    multiscales = read_multiscales(group)
    if not multiscales:
        raise CliError(f"No multiscales metadata found in {zarr_path}.")

    existing_datasets = multiscales[0]["datasets"]
    # By this codebase's own convention (research.md), datasets[0] is the finest.
    finest = existing_datasets[0]
    finest_scale = next(
        t["scale"] for t in finest["coordinateTransformations"] if t["type"] == "scale"
    )

    finest_array = group[finest["path"]]
    if not isinstance(finest_array, zarr.Array):
        raise CliError(f"{finest['path']!r} is not an array in this dataset.")

    new_paths = next_new_paths(existing_datasets, num_levels)
    new_levels: list[NewLevel] = []
    source_array: da.Array = da.from_array(finest_array, chunks=finest_array.chunks)
    source_scale = list(finest_scale)
    source_chunks = finest_array.chunks
    for path in new_paths:
        upsampled = _upsample_once(source_array)
        if smooth is not None:
            smoothed_np = _smooth_labels(upsampled.compute(), smooth)
            upsampled = da.from_array(smoothed_np, chunks=source_chunks)
        new_scale = [s / 2 for s in source_scale]
        new_levels.append(
            NewLevel(path=path, array=upsampled, chunks=source_chunks, scale=new_scale)
        )
        source_array = upsampled
        source_scale = new_scale

    # Finer levels were built outward from the existing finest level (each new
    # level upsampling the one before it), so new_levels is ordered
    # least-fine-new-level-first -- reverse so the *most* fine is listed
    # first, matching this codebase's finest-first `datasets` convention
    # (commit_new_levels() prepends this list as-is).
    new_levels.reverse()
    return new_levels


@click.command(name="upsample")
@click.argument("zarr_path", type=ZarrPathParamType(exists=True, file_okay=False))
@click.option(
    "--num_levels",
    type=int,
    default=1,
    show_default=True,
    help="Number of new, progressively finer levels to add.",
)
@click.option(
    "--smooth",
    type=float,
    default=None,
    help=(
        "Gaussian sigma to soften label boundaries with. Every voxel of the "
        "result is still snapped to one of the original label values -- never "
        "a blurred/non-discrete value. Omit for no smoothing."
    ),
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Write the extended dataset to this new path instead of upsampling "
        "ZARR_PATH in place; ZARR_PATH is left completely untouched. Must not "
        "already exist. Omit to upsample ZARR_PATH in place (default)."
    ),
)
def upsample(zarr_path: str, num_levels: int, smooth: float | None, output: str | None) -> None:
    """Add finer multiscale levels above ZARR_PATH's existing finest level.

    Meant for label/mask datasets: new levels are built by exact
    nearest-neighbor expansion, never interpolation, so every voxel's value
    is always one already present in the source data.
    """
    if num_levels < 1:
        raise CliError("--num_levels must be at least 1.")
    output_path = Path(output) if output else None
    validate_output_path(output_path)

    path = Path(zarr_path)
    new_levels = _build_new_finer_levels(path, num_levels, smooth)

    if output_path is not None:
        shutil.copytree(path, output_path)
        target_path = output_path
    else:
        target_path = path

    target_group = zarr.open_group(str(target_path), mode="r+")
    commit_new_levels(target_path, target_group, new_levels, position="prepend")

    click.echo(f"Added {num_levels} finer level(s) to {target_path}.")
