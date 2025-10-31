from pathlib import Path
import click
import zarr
import numpy as np
import dask.array as da
import joblib
import shutil
import tempfile
import skimage.measure


# ------------------------------------------------------------------------------
# Upsampling utilities
# ------------------------------------------------------------------------------

@joblib.delayed
def _copy(
    arr_in: zarr.Array,
    arr_out: zarr.Array,
    x: int,
    y: int,
    z: int,
    upsample_factor: int,
) -> None:
    """Copy a chunk and upsample by factor using nearest-neighbor repeat."""
    source = arr_in[
        x : x + arr_in.chunks[0],
        y : y + arr_in.chunks[1],
        z : z + arr_in.chunks[2],
    ]
    if np.all(source == arr_in.fill_value):
        return

    arr_out[
        x * upsample_factor : (x + arr_in.chunks[0]) * upsample_factor,
        y * upsample_factor : (y + arr_in.chunks[1]) * upsample_factor,
        z * upsample_factor : (z + arr_in.chunks[2]) * upsample_factor,
    ] = (
        np.array(source)
        .repeat(upsample_factor, axis=0)
        .repeat(upsample_factor, axis=1)
        .repeat(upsample_factor, axis=2)
    )


def upsample_mask(mask_da: da.Array, factor: int = 2) -> da.Array:
    """Upsample by factor 2 using nearest-neighbor repeat (lazy)."""
    if factor != 2:
        raise ValueError("Only upsample factor 2 is supported.")
    return (
        mask_da
        .repeat(factor, axis=0)
        .repeat(factor, axis=1)
        .repeat(factor, axis=2)
    )


# ------------------------------------------------------------------------------
# Downsampling utilities (stack-to-chunk style)
# ------------------------------------------------------------------------------

def downsample_mask(mask_da: da.Array, factor: int = 2) -> da.Array:
    """
    Downsample lazily by local mean pooling (stack-to-chunk style) using skimage.block_reduce.
    """
    if factor != 2:
        raise ValueError("Only downsample factor 2 is supported.")
    # skimage.block_reduce is not lazy, so we use Dask-map_blocks wrapper
    def _reduce_block(block):
        # pad to even dimensions
        pads = np.array(block.shape) % factor
        pad_width = [(0, p) for p in pads]
        block = np.pad(block, pad_width, mode="edge")
        return skimage.measure.block_reduce(block, block_size=(2, 2, 2), func=np.mean)

    new_chunks = tuple(max(1, c // factor) for c in mask_da.chunksize)
    return mask_da.map_blocks(_reduce_block, dtype=mask_da.dtype, chunks=new_chunks)


# ------------------------------------------------------------------------------
# Main CLI
# ------------------------------------------------------------------------------

@click.command()
@click.option("--volume", required=True, type=click.Path(exists=True, file_okay=False),
              help="Path to OME-Zarr volume.")
@click.option("--mask", required=True, type=click.Path(exists=True, file_okay=False),
              help="Path to OME-Zarr mask.")
@click.option("--threshold", default=0.5, show_default=True, type=float,
              help="Threshold to binarize the mask.")
@click.option("--temporary_upsample", is_flag=True,
              help="Use a temporary directory for mask upsampling.")
def apply_mask(volume, mask, threshold, temporary_upsample):
    """
    Apply a binary mask to an OME-Zarr volume.

    Both inputs must be OME-Zarr directories.
    One of the scales must match; the mask is upsampled or downsampled
    by a factor 2 as needed, then applied lazily to all scales.
    """
    volume_path = Path(volume)
    mask_path = Path(mask)

    click.echo(f"Applying mask {mask_path} → {volume_path}")
    volume_store = zarr.open_group(volume_path, mode="r+")
    mask_store = zarr.open_group(mask_path, mode="r")

    # Find a matching scale
    matching_scale = next((k for k in volume_store.keys() if k in mask_store), None)
    if matching_scale is None:
        raise click.ClickException("No matching scale between volume and mask.")
    click.echo(f"Using matching scale: {matching_scale}")

    vol_arr = da.from_zarr(volume_store[matching_scale])
    mask_arr = da.from_zarr(mask_store[matching_scale])

    # Binarize mask
    mask_da = (mask_arr > threshold).astype(np.uint8)

    # Match resolutions
    if mask_da.shape < vol_arr.shape:
        click.echo("Upsampling mask by factor 2...")
        mask_da = upsample_mask(mask_da)
    elif mask_da.shape > vol_arr.shape:
        click.echo("Downsampling mask by factor 2...")
        mask_da = downsample_mask(mask_da)

    # Apply lazily to all scales
    for scale_key, vol_z in volume_store.items():
        click.echo(f"Applying mask to scale {scale_key}...")
        vol_da = da.from_zarr(vol_z)

        if vol_da.shape != mask_da.shape:
            click.echo(f"Skipping {scale_key} (shape mismatch)")
            continue

        masked_da = vol_da * mask_da
        masked_da.to_zarr(vol_z.store, overwrite=True, compute=True)

    click.echo("Mask application complete.")


if __name__ == "__main__":
    apply_mask()
