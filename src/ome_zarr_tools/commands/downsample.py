from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from pathlib import Path

import click
import dask.array as da
import numpy.typing as npt
import skimage.transform
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.pyramid import NewLevel, commit_new_levels, next_new_paths
from ome_zarr_tools.core.resample import intensity_downsample, label_downsample
from ome_zarr_tools.core.zarr_path import ZarrPathParamType, validate_output_path
from ome_zarr_tools.io.ome_metadata import read_multiscales


def _build_coarser_levels(
    zarr_path: Path,
    num_levels: int,
    *,
    label: bool,
    downsample_func: Callable[..., Iterable[npt.NDArray]] = skimage.transform.pyramid_gaussian,
) -> list[NewLevel]:
    """Read ``zarr_path``'s existing coarsest level and build ``num_levels``
    new, progressively coarser levels below it, each built from the one
    before via ``core.resample.label_downsample`` (``label=True``) -- the
    same label-safe per-channel-argmax primitive ``apply_mask`` uses to
    align a mask's resolution, instead of Gaussian-blending raw label values
    together -- or ``core.resample.intensity_downsample`` (``label=False``,
    the default), which applies ``downsample_func`` (Gaussian-pyramid
    antialiasing by default) directly to continuous data. Both stay lazy
    (dask, chunk-wise) throughout; ``commit_new_levels`` is what actually
    triggers computation, in one combined batch across every new level.
    """
    group = zarr.open_group(str(zarr_path), mode="r")
    multiscales = read_multiscales(group)
    if not multiscales:
        raise CliError(f"No multiscales metadata found in {zarr_path}.")

    existing_datasets = multiscales[0]["datasets"]
    # By this codebase's own convention (research.md), datasets[-1] is the coarsest.
    coarsest = existing_datasets[-1]
    coarsest_scale = next(
        t["scale"] for t in coarsest["coordinateTransformations"] if t["type"] == "scale"
    )

    coarsest_array = group[coarsest["path"]]
    if not isinstance(coarsest_array, zarr.Array):
        raise CliError(f"{coarsest['path']!r} is not an array in this dataset.")

    downsample = label_downsample if label else intensity_downsample

    new_paths = next_new_paths(existing_datasets, num_levels, group=group)
    new_levels = []
    data = da.from_array(coarsest_array, chunks=coarsest_array.chunks)
    for i, path in enumerate(new_paths):
        data = downsample(data, downsample_func=downsample_func)
        chunk_shape = tuple(
            min(chunk, size) for chunk, size in zip(coarsest_array.chunks, data.shape, strict=True)
        )
        new_levels.append(
            NewLevel(
                path=path,
                array=data,
                chunks=chunk_shape,
                scale=[s * 2 ** (i + 1) for s in coarsest_scale],
            )
        )
    return new_levels


@click.command(name="downsample")
@click.argument("zarr_path", type=ZarrPathParamType(exists=True, file_okay=False))
@click.option(
    "--num_levels",
    type=int,
    default=1,
    show_default=True,
    help="Number of new, progressively coarser levels to add.",
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Write the extended dataset to this new path instead of downsampling "
        "ZARR_PATH in place; ZARR_PATH is left completely untouched. Must not "
        "already exist. Omit to downsample ZARR_PATH in place (default)."
    ),
)
@click.option(
    "--label",
    is_flag=True,
    help=(
        "Treat ZARR_PATH as label/segmentation data: downsample each distinct "
        "label value as its own probability channel and take the per-voxel "
        "argmax, instead of Gaussian-blending label values together the way "
        "the default continuous-intensity downsampling would."
    ),
)
def downsample(zarr_path: str, num_levels: int, output: str | None, label: bool) -> None:
    """Add coarser multiscale levels below ZARR_PATH's existing coarsest level."""
    if num_levels < 1:
        raise CliError("--num_levels must be at least 1.")
    output_path = Path(output) if output else None
    validate_output_path(output_path)

    path = Path(zarr_path)
    new_levels = _build_coarser_levels(path, num_levels, label=label)

    if output_path is not None:
        shutil.copytree(path, output_path)
        target_path = output_path
    else:
        target_path = path

    target_group = zarr.open_group(str(target_path), mode="r+")
    commit_new_levels(target_path, target_group, new_levels, position="append")

    click.echo(f"Added {num_levels} coarser level(s) to {target_path}.")
