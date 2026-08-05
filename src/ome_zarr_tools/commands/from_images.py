from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.io.images import read_stack, read_volume
from ome_zarr_tools.io.ome_metadata import add_half_pixel_translations


def _level_shapes(shape: tuple[int, ...], num_downsampling: int) -> list[tuple[int, ...]]:
    levels = [tuple(shape)]
    for _ in range(num_downsampling):
        levels.append(tuple(max(1, s // 2) for s in levels[-1]))
    return levels


@click.command(name="from_images")
@click.option(
    "--stack_dir",
    type=click.Path(exists=True, file_okay=False),
    default=None,
    help="Directory of same-type 2D slice files.",
)
@click.option(
    "--stack_pattern",
    type=str,
    default=None,
    help='Glob pattern expanded by Python (e.g. "/path/to/stack/*.jp2").',
)
@click.option(
    "--vol_file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to a single 3D image file.",
)
@click.option(
    "--voxel_size",
    "--resolution",
    "voxel_size",
    multiple=True,
    type=float,
    required=True,
    help=(
        "Voxel size: pass once for isotropic voxels, or three times (once per "
        "z/y/x axis), e.g. --voxel_size 1.0 --voxel_size 1.0 --voxel_size 2.0."
    ),
)
@click.option(
    "--voxel_size_unit",
    "--resolution_unit",
    "voxel_size_unit",
    default="micrometer",
    show_default=True,
    help="Unit for voxel size.",
)
@click.option(
    "--num_downsampling",
    type=int,
    default=0,
    show_default=True,
    help="Number of downsampled pyramid levels below full resolution.",
)
@click.option(
    "--chunk_size",
    type=int,
    default=64,
    show_default=True,
    help="Isotropic chunk edge length.",
)
@click.argument("output_zarr", type=click.Path())
def from_images(
    stack_dir: str | None,
    stack_pattern: str | None,
    vol_file: str | None,
    voxel_size: tuple[float, ...],
    voxel_size_unit: str,
    num_downsampling: int,
    chunk_size: int,
    output_zarr: str,
) -> None:
    """Convert a 2D image stack or a 3D volume file to OME-Zarr at OUTPUT_ZARR."""
    sources = [s for s in (stack_dir, stack_pattern, vol_file) if s]
    if len(sources) != 1:
        raise CliError("Specify exactly one of --stack_dir, --stack_pattern, or --vol_file.")

    if len(voxel_size) not in (1, 3):
        raise CliError("--voxel_size must be given as 1 or 3 values.")
    voxel_size_tuple = tuple(voxel_size) * 3 if len(voxel_size) == 1 else tuple(voxel_size)

    if vol_file:
        click.echo(f"Using 3D image file: {vol_file}")
        arr = read_volume(Path(vol_file))
    else:
        click.echo(f"Using {'directory' if stack_dir else 'pattern'}: {stack_dir or stack_pattern}")
        arr = read_stack(Path(stack_dir) if stack_dir else None, stack_pattern)

    arr = arr.rechunk(chunk_size)
    click.echo(f"Converting to OME-Zarr at {output_zarr} (shape={arr.shape})")

    level_shapes = _level_shapes(arr.shape, num_downsampling)

    try:
        from bioio_ome_zarr.writers import OMEZarrWriter
    except ImportError as exc:
        raise CliError(f"bioio-ome-zarr is not installed: {exc}") from exc

    writer = OMEZarrWriter(
        str(output_zarr),
        level_shapes=level_shapes,
        dtype=arr.dtype,
        chunk_shape=(chunk_size,) * 3,
        zarr_format=2,
        image_name="Image",
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=[voxel_size_unit] * 3,
        physical_pixel_size=list(voxel_size_tuple),
    )
    writer.initialize()
    writer.write_full_volume(arr)

    group = zarr.open_group(str(output_zarr), mode="r+")
    attrs = dict(group.attrs)
    multiscales = cast("list[dict[str, Any]]", attrs["multiscales"])
    multiscales[0]["datasets"] = add_half_pixel_translations(multiscales[0]["datasets"])
    group.attrs.put(attrs)

    click.echo(
        f"Saved OME-Zarr at {output_zarr} with shape {arr.shape} "
        f"and {num_downsampling} downsampled level(s)"
    )
