from pathlib import Path
import logging
from typing import Tuple

import click
import zarr
import numpy as np
import dask.array as da
import skimage.measure

LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Upsampling / downsampling utilities
# ------------------------------------------------------------------------------


def upsample_mask(mask_da: da.Array, factor: int = 2) -> da.Array:
    """Upsample by integer factor using nearest-neighbor repeat (lazy).

    Currently only factor == 2 is supported to match the rest of the package
    expectations (pyramidal scales differing by factor 2).
    """
    if factor != 2:
        raise ValueError("Only upsample factor 2 is supported.")
    return (
        mask_da
        .repeat(factor, axis=0)
        .repeat(factor, axis=1)
        .repeat(factor, axis=2)
    )


def downsample_mask(mask_da: da.Array, factor: int = 2) -> da.Array:
    """
    Downsample lazily by local mean pooling (stack-to-chunk style) using
    skimage.measure.block_reduce.

    The implementation wraps block_reduce inside a map_blocks call so the overall
    operation remains lazy and can be executed by Dask.
    """
    if factor != 2:
        raise ValueError("Only downsample factor 2 is supported.")

    def _reduce_block(block: np.ndarray) -> np.ndarray:
        # pad to even dimensions so block_reduce with block_size=(2,2,2) works
        pads = np.array(block.shape) % factor
        pad_width = [(0, int(p)) for p in pads]
        if any(p != 0 for p in pads):
            block = np.pad(block, pad_width, mode="edge")
        return skimage.measure.block_reduce(block, block_size=(2, 2, 2), func=np.mean)

    # derive new chunks from existing dask chunks (each entry in mask_da.chunks is a tuple)
    new_chunks: Tuple[int, ...] = tuple(max(1, c[0] // factor) for c in mask_da.chunks)
    return mask_da.map_blocks(_reduce_block, dtype=mask_da.dtype, chunks=new_chunks)


# ------------------------------------------------------------------------------
# Main CLI
# ------------------------------------------------------------------------------


@click.command()
@click.option(
    "--volume",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to OME-Zarr volume.",
)
@click.option(
    "--mask",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to OME-Zarr mask.",
)
@click.option(
    "--threshold",
    default=0.5,
    show_default=True,
    type=float,
    help="Threshold to binarize the mask.",
)
@click.option(
    "--temporary_upsample",
    is_flag=True,
    help="(Unused) kept for CLI compatibility with other tools.",
)
def apply_mask(volume: str, mask: str, threshold: float, temporary_upsample: bool) -> None:
    """
    Apply a binary mask to an OME-Zarr volume.

    Both inputs must be OME-Zarr directories. One of the scales must match; the
    mask is upsampled or downsampled by a factor 2 as needed, then applied lazily
    to all scales.
    """
    volume_path = Path(volume)
    mask_path = Path(mask)

    click.echo(f"Applying mask {mask_path} → {volume_path}")
    volume_store = zarr.open_group(volume_path, mode="r+")
    mask_store = zarr.open_group(mask_path, mode="r")

    # Find a matching scale key that exists in both stores
    matching_scale = next((k for k in volume_store.keys() if k in mask_store), None)
    if matching_scale is None:
        raise click.ClickException("No matching scale between volume and mask.")
    click.echo(f"Using matching scale: {matching_scale}")

    vol_arr = da.from_zarr(volume_store[matching_scale])
    mask_arr = da.from_zarr(mask_store[matching_scale])

    # Binarize mask
    mask_da = (mask_arr > threshold).astype(np.uint8)

    # Match resolutions between mask and volume: either upsample or downsample
    if mask_da.shape < vol_arr.shape:
        click.echo("Upsampling mask by factor 2...")
        mask_da = upsample_mask(mask_da)
    elif mask_da.shape > vol_arr.shape:
        click.echo("Downsampling mask by factor 2...")
        mask_da = downsample_mask(mask_da)

    # Apply lazily to all scales present in the volume store
    for scale_key, vol_z in volume_store.items():
        click.echo(f"Applying mask to scale {scale_key}...")
        vol_da = da.from_zarr(vol_z)

        if vol_da.shape != mask_da.shape:
            click.echo(f"Skipping {scale_key} (shape mismatch)")
            continue

        masked_da = vol_da * mask_da

        # Write masked data back to the same zarr array. Use the array's store and
        # path (component) so we target the same array inside the group.
        # to_zarr is invoked with compute=True so the operation runs here.
        masked_da.to_zarr(vol_z.store, component=vol_z.path, overwrite=True, compute=True)

    click.echo("Mask application complete.")


if __name__ == "__main__":
    apply_mask()
