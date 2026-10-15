from __future__ import annotations

from pathlib import Path
from typing import Literal

import click
import zarr

from ome_zarr_tools.commands.migrate import DEFAULT_TARGET_VERSION, validate_chunks_per_shard
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.pyramid import write_new_pyramid
from ome_zarr_tools.io.images import read_stack, read_volume
from ome_zarr_tools.io.ome_metadata import (
    add_half_pixel_translations,
    read_multiscales,
    write_multiscales,
)

_ZARR_FORMAT_BY_TARGET_VERSION: dict[str, Literal[2, 3]] = {"0.4": 2, "0.5": 3}
"""OME-NGFF version -> Zarr storage format, matching ``migrate.py``'s convention
(0.4 -> Zarr v2, 0.5 -> Zarr v3)."""


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
    "--num_levels",
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
@click.option(
    "--target_version",
    type=click.Choice(sorted(_ZARR_FORMAT_BY_TARGET_VERSION)),
    default=DEFAULT_TARGET_VERSION,
    show_default=True,
    help=(
        "OME-NGFF specification version to write. Implies the Zarr storage "
        "format (0.4 -> Zarr v2, 0.5 -> Zarr v3) -- not independently selectable."
    ),
)
@click.option(
    "--chunks_per_shard",
    type=int,
    default=None,
    help=(
        "Chunks per shard, per axis (isotropic). Requires --target_version 0.5 "
        "-- Zarr v2 (0.4) has no concept of shards. Omit for no sharding."
    ),
)
@click.argument("output_zarr", type=click.Path())
def from_images(
    stack_dir: str | None,
    stack_pattern: str | None,
    vol_file: str | None,
    voxel_size: tuple[float, ...],
    voxel_size_unit: str,
    num_levels: int,
    chunk_size: int,
    target_version: str,
    chunks_per_shard: int | None,
    output_zarr: str,
) -> None:
    """Convert a 2D image stack or a 3D volume file to OME-Zarr at OUTPUT_ZARR."""
    sources = [s for s in (stack_dir, stack_pattern, vol_file) if s]
    if len(sources) != 1:
        raise CliError("Specify exactly one of --stack_dir, --stack_pattern, or --vol_file.")

    if len(voxel_size) not in (1, 3):
        raise CliError("--voxel_size must be given as 1 or 3 values.")
    voxel_size_tuple = tuple(voxel_size) * 3 if len(voxel_size) == 1 else tuple(voxel_size)

    validate_chunks_per_shard(target_version, chunks_per_shard)

    if vol_file:
        click.echo(f"Using 3D image file: {vol_file}")
        arr = read_volume(Path(vol_file))
    else:
        click.echo(f"Using {'directory' if stack_dir else 'pattern'}: {stack_dir or stack_pattern}")
        arr = read_stack(Path(stack_dir) if stack_dir else None, stack_pattern)

    click.echo(f"Converting to OME-Zarr at {output_zarr} (shape={arr.shape})")

    write_new_pyramid(
        Path(output_zarr),
        arr,
        num_levels,
        axes_names=["z", "y", "x"],
        axes_types=["space", "space", "space"],
        axes_units=[voxel_size_unit] * 3,
        voxel_size=list(voxel_size_tuple),
        chunk_shape=(chunk_size,) * 3,
        shard_shape=(chunks_per_shard * chunk_size,) * 3 if chunks_per_shard is not None else None,
        zarr_format=_ZARR_FORMAT_BY_TARGET_VERSION[target_version],
        image_name="Image",
    )

    group = zarr.open_group(str(output_zarr), mode="r+")
    multiscales = read_multiscales(group)
    assert multiscales is not None  # the writer above always emits multiscales metadata
    multiscales[0]["datasets"] = add_half_pixel_translations(multiscales[0]["datasets"])
    write_multiscales(group, multiscales)

    click.echo(
        f"Saved OME-Zarr at {output_zarr} with shape {arr.shape} "
        f"and {num_levels} downsampled level(s)"
    )
