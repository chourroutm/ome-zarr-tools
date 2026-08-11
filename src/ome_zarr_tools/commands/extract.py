from __future__ import annotations

import os
from pathlib import Path

import click
import dask.array as da
import imageio.v3 as iio
import numpy as np
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.zarr_path import ZarrPathParamType
from ome_zarr_tools.io.ome_metadata import read_multiscales


@click.command()
@click.argument("zarr_path", type=ZarrPathParamType(exists=True, file_okay=False))
@click.option(
    "--corner",
    nargs=3,
    type=int,
    multiple=True,
    help=(
        "Corner coordinates (i, j, k). Can be specified once (start corner) with "
        "--size, or twice (start and end corners, in any order)."
    ),
)
@click.option("--size", nargs=3, type=int, default=None, help="Size (isize, jsize, ksize).")
@click.option("--center", nargs=3, type=int, default=None, help="Center coordinates (i, j, k).")
@click.option("--halfsize", type=int, default=None, help="Half-size (in voxels) around the center.")
@click.option(
    "--mag", type=float, default=None, help="Magnification level (1=original, 2=downsampled once)."
)
@click.option(
    "--level",
    "--mip",
    "--dataset_path",
    "level",
    type=int,
    default=0,
    show_default=True,
    help="Index into the dataset's resolution levels (0=highest resolution).",
)
@click.option(
    "--scale", type=float, default=None, help="Scaling factor (1=original, 0.5=downsampled once)."
)
@click.option("--output", type=click.Path(), default=None, help="Output file path.")
@click.option(
    "--output_format",
    type=str,
    default=".ome.tif",
    show_default=True,
    help="Output format (.tif, .ome.tif, .nii, .nii.gz, .raw, etc.).",
)
def extract(
    zarr_path: str,
    corner: tuple[tuple[int, int, int], ...],
    size: tuple[int, int, int] | None,
    center: tuple[int, int, int] | None,
    halfsize: int | None,
    mag: float | None,
    level: int,
    scale: float | None,
    output: str | None,
    output_format: str,
) -> None:
    """Extract a whole scale or a crop from an OME-Zarr pyramid.

    Examples:
      extract data.zarr --corner 0 0 0 --size 512 512 256
      extract data.zarr --corner 0 0 0 --corner 512 512 256
      extract data.zarr --center 256 256 128 --halfsize 128
    """
    if mag and not scale:
        scale = 1.0 / mag
    elif scale and not mag:
        mag = 1.0 / scale

    try:
        group = zarr.open_group(zarr_path, mode="r")
    except Exception as exc:
        raise CliError(f"No Zarr group found at {zarr_path}. Details: {exc}") from exc
    multiscales = read_multiscales(group)
    if not multiscales:
        raise CliError(f"No multiscales metadata found in {zarr_path}.")
    datasets = multiscales[0].get("datasets", [])
    if not (0 <= level < len(datasets)):
        raise CliError(f"Level {level} not found; dataset has levels 0-{len(datasets) - 1}.")
    dataset_path = datasets[level]["path"]
    data = da.from_zarr(group[dataset_path])

    if len(corner) == 2:
        c0, c1 = np.array(corner[0]), np.array(corner[1])
        cmin, cmax = np.minimum(c0, c1), np.maximum(c0, c1)
        corner_val, size_val = cmin.tolist(), (cmax - cmin).tolist()
    elif len(corner) == 1:
        if not size:
            raise CliError("When one --corner is given, --size must also be specified.")
        corner_val, size_val = list(corner[0]), list(size)
    elif center and halfsize:
        corner_val = [c - halfsize for c in center]
        size_val = [2 * halfsize] * 3
    elif corner and not size:
        raise CliError("--corner requires --size when not providing two corners.")
    elif size and not corner:
        raise CliError("--size requires --corner to be specified.")
    else:
        corner_val = [0, 0, 0]
        size_val = list(data.shape[-3:])

    i0, j0, k0 = (int(v) for v in corner_val)
    isize, jsize, ksize = (int(v) for v in size_val)

    click.echo(f"Reading dataset {zarr_path} [level={level}] ...")
    region = data[k0 : k0 + ksize, j0 : j0 + jsize, i0 : i0 + isize]
    arr = region.compute()

    if not output:
        base = os.path.splitext(str(zarr_path).rstrip("/"))[0]
        output = f"{base}_level{level}{output_format}"

    click.echo(f"Extracting region corner={corner_val}, size={size_val}")
    click.echo(f"Writing output to {output} ...")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(output, np.asarray(arr))
    click.echo(f"Extraction complete: {output}")
