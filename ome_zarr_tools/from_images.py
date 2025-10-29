import click
import os
import glob
import dask.array as da

@click.command()
@click.option("--stack_dir", type=click.Path(exists=True), required=False,
              help="Path to directory with one type of files as slices (2D stack).")
@click.option("--stack_files", multiple=True, type=click.Path(exists=True), required=False,
              help="Shell-expanded list of filenames as slices (2D stack).")
@click.option("--stack_pattern", type=str, required=False,
              help='String with a wildcard that gets expanded by Python (e.g. "/path/to/stack/*.jp2").')
@click.option("--vol_file", type=click.Path(exists=True), required=False,
              help="Path to file as 3D image.")
@click.option("--voxel_size", "--resolution", multiple=True, type=float, required=False,
              help="Voxel size or resolution as a tuple (e.g. --voxel_size 1.0 1.0 2.0).")
@click.option("--voxel_size_unit", "--resolution_unit", default="micrometer", required=False,
              help="Unit for voxel size/resolution (default: micrometer).")
@click.option("--axis_order", type=str, required=False,
              help='Axis order string, e.g. "ZYX".')
@click.argument("output_zarr", type=click.Path())
def from_images(stack_dir, stack_files, stack_pattern, vol_file,
                voxel_size, voxel_size_unit, axis_order, output_zarr):
    """
    Convert images from a stack of 2D slices or a 3D image file to OME-Zarr format at OUTPUT_ZARR
    using stack-to-chunk for correct chunking and metadata.
    """
    # --- Find image sources ---
    sources = []
    if stack_dir:
        sources = sorted([os.path.join(stack_dir, fname) for fname in os.listdir(stack_dir)])
        click.echo(f"Using all slices in directory: {stack_dir}")
    elif stack_files:
        sources = list(stack_files)
        click.echo(f"Using explicit list of slice files: {sources}")
    elif stack_pattern:
        sources = sorted(glob.glob(stack_pattern))
        click.echo(f"Using pattern '{stack_pattern}' expanded to: {sources}")
    elif vol_file:
        sources = [vol_file]
        click.echo(f"Using 3D image file: {vol_file}")
    else:
        raise click.UsageError("You must specify at least one of --stack_dir, --stack_files, --stack_pattern, or --vol_file.")

    click.echo(f"Voxel size: {voxel_size if voxel_size else 'Not specified'}")
    click.echo(f"Voxel size unit: {voxel_size_unit}")
    click.echo(f"Axis order: {axis_order if axis_order else 'Not specified'}")
    click.echo(f"Converting to OME-Zarr at {output_zarr}")

    # --- Build dask array from input ---
    if vol_file:
        # Use dask-image for large 3D files; fallback to dask from numpy if not
        try:
            import dask_image.imread
            arr = dask_image.imread.imread(vol_file)
        except ImportError:
            import imageio.v3 as iio
            import numpy as np
            arr = da.from_array(iio.imread(vol_file), chunks="auto")
    else:
        # Use dask-image to read stack of images
        try:
            import dask_image.imread
            arr = dask_image.imread.imread(sources)
            # dask-image reads shape (n, y, x), stack-to-chunk expects (y, x, z)
            arr = arr.transpose(1, 2, 0)
        except ImportError:
            import imageio.v3 as iio
            import numpy as np
            imgs = [iio.imread(f) for f in sources]
            arr = da.from_array(np.stack(imgs, axis=-1), chunks="auto")

    # --- Use stack-to-chunk to convert to OME-Zarr ---
    # The chunk size can be configurable; here we use (64, 64, 64) for demo
    chunk_shape = (64, 64, 64)
    # The axis order is assumed to be ZYX unless specified
    axis_names = list(axis_order) if axis_order else ["z", "y", "x"]
    # stack-to-chunk expects voxel_size as a tuple of 3 floats
    voxel_size_tuple = tuple(voxel_size) if voxel_size else (1.0, 1.0, 1.0)

    # Import stack-to-chunk API
    try:
        from stack_to_chunk import MultiScaleGroup
        from pydantic_zarr.v3 import NamedConfig, ArraySpec
    except ImportError:
        raise click.ClickException("stack-to-chunk is not installed. Please install it to use this feature.")

    # Make the ArraySpec for stack-to-chunk
    array_spec = ArraySpec.from_array(
        arr,
        chunk_grid=NamedConfig(
            name="regular",
            configuration={"chunk_shape": list(chunk_shape)}
        ),
        codecs=(NamedConfig(name="bytes"), NamedConfig(name="zstd", configuration={"level": 2}))
    )

    # Create the MultiScaleGroup and add full resolution data
    group = MultiScaleGroup(
        output_zarr,
        name="ome_zarr",
        spatial_unit=voxel_size_unit,
        voxel_size=voxel_size_tuple,
        array_spec=array_spec,
    )
    group.add_full_res_data(arr, n_processes=1)

    click.echo(f"Saved OME-Zarr at {output_zarr} with shape {arr.shape}")