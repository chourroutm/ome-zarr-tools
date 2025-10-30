import click
import os
import numpy as np
import dask.array as da
import imageio.v3 as iio
import zarr


@click.group()
def cli():
    """OME-Zarr extraction utility."""
    pass


@cli.command()
@click.argument("zarr_path", type=click.Path(exists=True))
@click.option(
    "--corner",
    nargs=3,
    type=int,
    multiple=True,
    help=(
        "Corner coordinates (i, j, k). Can be specified once (start corner) with --size, "
        "or twice (start and end corners, in any order)."
    ),
)
@click.option("--size", nargs=3, type=int, help="Size (isize, jsize, ksize).")
@click.option("--center", nargs=3, type=int, help="Center coordinates (i, j, k).")
@click.option("--halfsize", type=int, help="Half-size (in voxels) around the center.")
@click.option("--mag", type=float, help="Magnification level (1=original, 2=downsampled once).")
@click.option("--mip", "--level", "--dataset_path", "level", type=int, help="Pyramid level (0=original).")
@click.option("--scale", type=float, help="Scaling factor (1=original, 0.5=downsampled once).")
@click.option("--output", type=click.Path(), help="Output file path.")
@click.option(
    "--output_format",
    type=str,
    default=".ome.tif",
    help="Output format (.tif, .ome.tif, .nii, .nii.gz, .raw, etc.).",
)
def extract(
    zarr_path,
    corner,
    size,
    center,
    halfsize,
    mag,
    level,
    scale,
    output,
    output_format,
):
    """
    Extract a whole scale or a crop from an OME-Zarr pyramid.

    Examples:
      extract data.zarr --corner 0 0 0 --size 512 512 256
      extract data.zarr --corner 0 0 0 --corner 512 512 256
      extract data.zarr --corner 512 512 256 --corner 0 0 0  # arbitrary order
      extract data.zarr --center 256 256 128 --halfsize 128
    """

    # --- Resolve scaling ---
    if mag and not scale:
        scale = 1.0 / mag
    elif scale and not mag:
        mag = 1.0 / scale
    elif not mag and not scale:
        mag = scale = 1.0

    if level is None:
        level = 0

    # --- Load dataset ---
    store = zarr.open(zarr_path, mode="r")
    dataset_key = f"{level}" if f"{level}" in store else None
    data = da.from_zarr(store[dataset_key] if dataset_key else store)

    # --- Determine crop region ---
    if len(corner) == 2:
        c0, c1 = np.array(corner[0]), np.array(corner[1])
        # make order independent
        cmin = np.minimum(c0, c1)
        cmax = np.maximum(c0, c1)
        corner = cmin.tolist()
        size = (cmax - cmin).tolist()
    elif len(corner) == 1:
        corner = list(corner[0])
        if not size:
            raise click.UsageError("When one --corner is given, --size must also be specified.")
        size = list(size)
    elif center and halfsize:
        corner = [c - halfsize for c in center]
        size = [2 * halfsize] * 3
    elif corner and not size:
        raise click.UsageError("--corner requires --size when not providing two corners.")
    elif size and not corner:
        raise click.UsageError("--size requires --corner to be specified.")
    else:
        # No crop → full dataset
        corner = (0, 0, 0)
        size = data.shape[-3:]

    # Validate
    i0, j0, k0 = map(int, corner)
    isize, jsize, ksize = map(int, size)

    # --- Extract region ---
    click.echo(f"Reading dataset {zarr_path} [level={level}] ...")
    region = data[k0 : k0 + ksize, j0 : j0 + jsize, i0 : i0 + isize]
    arr = region.compute()

    # --- Output handling ---
    if not output:
        base = os.path.splitext(zarr_path.rstrip("/"))[0]
        output = f"{base}_level{level}{output_format}"

    click.echo(f"Extracting region corner={corner}, size={size}")
    click.echo(f"Writing output to {output} ...")

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    iio.imwrite(output, np.asarray(arr))
    click.echo(f"✅ Extraction complete: {output}")


if __name__ == "__main__":
    cli()
