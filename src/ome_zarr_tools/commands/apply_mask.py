from __future__ import annotations

from pathlib import Path

import click
import dask.array as da
import numpy as np
import skimage.measure
import zarr

from ome_zarr_tools.core.backup import backup_attrs
from ome_zarr_tools.core.errors import CliError


def upsample_mask(mask_da: da.Array, factor: int = 2) -> da.Array:
    """Upsample by integer factor using nearest-neighbor repeat (lazy)."""
    if factor != 2:
        raise ValueError("Only upsample factor 2 is supported.")
    return mask_da.repeat(factor, axis=0).repeat(factor, axis=1).repeat(factor, axis=2)


def downsample_mask(mask_da: da.Array, factor: int = 2) -> da.Array:
    """Downsample lazily by local mean pooling using ``skimage.measure.block_reduce``."""
    if factor != 2:
        raise ValueError("Only downsample factor 2 is supported.")

    def _reduce_block(block: np.ndarray) -> np.ndarray:
        pads = np.array(block.shape) % factor
        if any(p != 0 for p in pads):
            block = np.pad(block, [(0, int(p)) for p in pads], mode="edge")
        return skimage.measure.block_reduce(block, block_size=(2, 2, 2), func=np.mean)

    new_chunks: tuple[int, ...] = tuple(max(1, c[0] // factor) for c in mask_da.chunks)
    return mask_da.map_blocks(_reduce_block, dtype=mask_da.dtype, chunks=new_chunks)  # type: ignore[call-arg,arg-type]


@click.command(name="apply_mask")
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
    help="Reserved for CLI compatibility; mask resampling is always applied automatically.",
)
def apply_mask(volume: str, mask: str, threshold: float, temporary_upsample: bool) -> None:
    """Apply a binary mask to an OME-Zarr volume, resampled to match each resolution level."""
    volume_path = Path(volume)
    mask_path = Path(mask)

    click.echo(f"Applying mask {mask_path} -> {volume_path}")
    volume_store = zarr.open_group(str(volume_path), mode="r+")
    mask_store = zarr.open_group(str(mask_path), mode="r")

    matching_scale = next((k for k in volume_store.keys() if k in mask_store), None)
    if matching_scale is None:
        raise CliError("No matching resolution level between volume and mask.")
    click.echo(f"Using matching scale: {matching_scale}")

    backup_path = backup_attrs(volume_path, volume_store)
    click.echo(f"Backed up existing root attributes to {backup_path}")

    vol_arr = da.from_zarr(volume_store[matching_scale])
    mask_arr = da.from_zarr(mask_store[matching_scale])

    mask_da = (mask_arr > threshold).astype(np.uint8)

    if mask_da.shape < vol_arr.shape:
        click.echo("Upsampling mask by factor 2...")
        mask_da = upsample_mask(mask_da)
    elif mask_da.shape > vol_arr.shape:
        click.echo("Downsampling mask by factor 2...")
        mask_da = downsample_mask(mask_da)

    for scale_key, vol_z in volume_store.arrays():
        click.echo(f"Applying mask to scale {scale_key}...")
        vol_da = da.from_zarr(vol_z)

        if vol_da.shape != mask_da.shape:
            click.echo(f"Skipping {scale_key} (shape mismatch)")
            continue

        masked_da = vol_da * mask_da
        masked_da.to_zarr(vol_z, compute=True)

    click.echo("Mask application complete.")
