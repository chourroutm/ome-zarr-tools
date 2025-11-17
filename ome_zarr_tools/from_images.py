import click
import os
import glob
import dask.array as da
from natsort import natsorted
from pims.api import UnknownFormatError
from pathlib import Path

import sys

sys.setrecursionlimit(10**6)

@click.command()
@click.option("--stack_dir", type=click.Path(exists=True), required=False,
              help="Path to directory with one type of files as slices (2D stack).")
@click.option("--stack_pattern", type=str, required=False,
              help='String with a wildcard that gets expanded by Python (e.g. "/path/to/stack/*.jp2").')
@click.option("--vol_file", type=click.Path(exists=True), required=False,
              help="Path to file as 3D image.")
@click.option("--voxel_size", "--resolution", multiple=True, type=float, required=True,
              help="Voxel size or resolution as a tuple (e.g. --voxel_size 1.0 1.0 2.0).")
@click.option("--voxel_size_unit", "--resolution_unit", default="micrometer", required=False,
              help="Unit for voxel size/resolution (default: micrometer).")
@click.option("--num_downsampling", default=0, required=False,
              help="Number of downsampled levels (default: 0).")
@click.option("--chunk_size", default=64, required=False,
              help="Chunk size (default: 64).")
@click.option("--num_processes", default=1, required=False,
              help="Number of processes (default: 1).")
@click.argument("output_zarr", type=click.Path())
def from_images(stack_dir, stack_pattern, vol_file,
                voxel_size, voxel_size_unit, num_downsampling, chunk_size, num_processes, output_zarr):
    """
    Convert images from a stack of 2D slices or a 3D image file to OME-Zarr format at OUTPUT_ZARR
    using stack-to-chunk for correct chunking and metadata.
    """
    # --- Find image sources ---
    sources = []
    if stack_dir:
        sources = natsorted([os.path.join(stack_dir, fname) for fname in os.listdir(stack_dir)])
        click.echo(f"Using all {len(sources)} files in directory: {stack_dir}")
        sources = Path(stack_dir) / "*"
    elif stack_pattern:
        sources = natsorted(glob.glob(stack_pattern))
        click.echo(f"Using pattern '{stack_pattern}' expanded to {len(sources)} files")
        sources = Path(stack_pattern)
    elif vol_file:
        sources = Path(vol_file)
        click.echo(f"Using 3D image file: {vol_file}")
    else:
        # raise click.UsageError("You must specify at least one of --stack_dir, --stack_files, --stack_pattern, or --vol_file.")
        raise click.UsageError("You must specify at least one of --stack_dir, --stack_pattern, or --vol_file.")

    click.echo(f"Voxel size: {voxel_size}")
    click.echo(f"Voxel size unit: {voxel_size_unit}")
    click.echo(f"Converting to OME-Zarr at {output_zarr}")

    chunk_shape = (chunk_size, chunk_size, 1)

    # --- Build dask array from input ---
    if vol_file:
        # Use dask-image for large 3D files; fallback to dask from numpy if not
        try:
            import dask_image.imread
            arr = dask_image.imread.imread(vol_file).rechunk(chunk_shape)
            arr = arr.transpose((2,1,0)).rechunk(chunk_shape)
        except (ImportError,UnknownFormatError) as e:
            import imageio.v3 as iio
            import numpy as np
            arr = da.from_array(iio.imread(vol_file), chunks=chunk_shape[::-1])
            arr = arr.transpose((2,1,0))
    else:
        # Use dask-image to read stack of images
        try:
            import dask_image.imread
            print("sol1")
            arr = dask_image.imread.imread(sources)
            arr = arr.transpose((2,1,0))
        except (ImportError,UnknownFormatError) as e:
            import imageio.v3 as iio
            import numpy as np
            print("sol2")
            imgs = [iio.imread(f) for f in sources]
            arr = da.from_array(np.stack(imgs, axis=-1), chunks=chunk_shape)

    # --- Use stack-to-chunk to convert to OME-Zarr ---
    chunk_shape = (chunk_size,) * 3
    voxel_size_tuple = tuple(voxel_size) if len(voxel_size) == 3 else tuple(voxel_size) * 3

    try:
        from stack_to_chunk import MultiScaleGroup, memory_per_process
        from pydantic_zarr.v2 import ArraySpec
    except ImportError:
        raise click.ClickException("stack-to-chunk is not installed. Please install it to use this feature.")

    array_spec = ArraySpec.from_array(arr, chunks=chunk_shape)

    bytes_per_process = memory_per_process(arr, chunk_size=chunk_shape[0])
    print(f"Each process will use {bytes_per_process / 1e6:.1f} MB")

    group = MultiScaleGroup(
        Path(output_zarr),
        name="my_group",
        spatial_unit=voxel_size_unit,
        voxel_size=voxel_size_tuple,
        array_spec=array_spec,
    )
    with click.progressbar(range(1+num_downsampling),
                       label='Generating multi-scale OME-Zarr dataset...') as bar:
        for level_id in bar:
            if level_id == 0:
                group.add_full_res_data(arr, n_processes=num_processes)
            else:
                group.add_downsample_level(level_id, n_processes=num_processes)

    click.echo(f"Saved OME-Zarr at {output_zarr} with shape {arr.shape} and {num_downsampling} downsampled levels")