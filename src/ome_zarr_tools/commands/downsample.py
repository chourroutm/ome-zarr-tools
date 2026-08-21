from __future__ import annotations

import shutil
from pathlib import Path

import click
import ngff_zarr as nz
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.pyramid import NewLevel, commit_new_levels, next_new_paths
from ome_zarr_tools.core.zarr_path import ZarrPathParamType, validate_output_path
from ome_zarr_tools.io.ome_metadata import read_multiscales


def _build_new_coarser_levels(zarr_path: Path, num_levels: int) -> list[NewLevel]:
    """Read ``zarr_path``'s existing coarsest level and build ``num_levels`` new,
    progressively coarser levels below it via ``ngff_zarr.to_multiscales()``.
    """
    group = zarr.open_group(str(zarr_path), mode="r")
    multiscales = read_multiscales(group)
    if not multiscales:
        raise CliError(f"No multiscales metadata found in {zarr_path}.")

    axes = multiscales[0]["axes"]
    dims = [axis["name"] for axis in axes]
    axes_units = {axis["name"]: axis["unit"] for axis in axes if axis.get("unit")}
    existing_datasets = multiscales[0]["datasets"]
    # By this codebase's own convention (research.md), datasets[-1] is the coarsest.
    coarsest = existing_datasets[-1]
    coarsest_scale = next(
        t["scale"] for t in coarsest["coordinateTransformations"] if t["type"] == "scale"
    )

    coarsest_array = group[coarsest["path"]]
    if not isinstance(coarsest_array, zarr.Array):
        raise CliError(f"{coarsest['path']!r} is not an array in this dataset.")

    image = nz.to_ngff_image(
        coarsest_array,
        dims=dims,
        scale=dict(zip(dims, coarsest_scale, strict=True)),
        translation=dict.fromkeys(dims, 0.0),
        name=multiscales[0].get("name", "Image"),
        axes_units=axes_units or None,
    )
    result = nz.to_multiscales(image, scale_factors=[2**i for i in range(1, num_levels + 1)])

    new_paths = next_new_paths(existing_datasets, num_levels)
    new_levels = []
    for path, new_image in zip(new_paths, result.images[1:], strict=True):
        chunk_shape = tuple(
            min(chunk, size)
            for chunk, size in zip(coarsest_array.chunks, new_image.data.shape, strict=True)
        )
        new_levels.append(
            NewLevel(
                path=path,
                array=new_image.data,
                chunks=chunk_shape,
                scale=[new_image.scale[d] for d in dims],
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
def downsample(zarr_path: str, num_levels: int, output: str | None) -> None:
    """Add coarser multiscale levels below ZARR_PATH's existing coarsest level."""
    if num_levels < 1:
        raise CliError("--num_levels must be at least 1.")
    output_path = Path(output) if output else None
    validate_output_path(output_path)

    path = Path(zarr_path)
    new_levels = _build_new_coarser_levels(path, num_levels)

    if output_path is not None:
        shutil.copytree(path, output_path)
        target_path = output_path
    else:
        target_path = path

    target_group = zarr.open_group(str(target_path), mode="r+")
    commit_new_levels(target_path, target_group, new_levels, position="append")

    click.echo(f"Added {num_levels} coarser level(s) to {target_path}.")
