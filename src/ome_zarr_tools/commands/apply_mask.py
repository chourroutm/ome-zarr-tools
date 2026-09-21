from __future__ import annotations

import shutil
from pathlib import Path

import click
import dask.array as da
import numpy as np
import zarr

from ome_zarr_tools.core.backup import backup_attrs
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.resample import label_downsample, nearest_upsample
from ome_zarr_tools.core.zarr_path import ZarrPathParamType, validate_output_path


@click.command(name="apply_mask")
@click.option(
    "--volume",
    required=True,
    type=ZarrPathParamType(exists=True, file_okay=False),
    help="Path to OME-Zarr volume.",
)
@click.option(
    "--mask",
    required=True,
    type=ZarrPathParamType(exists=True, file_okay=False),
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
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Write the masked volume to this new path instead of masking --volume "
        "in place; --volume is left completely untouched. Must not already "
        "exist. Omit to mask --volume in place (default)."
    ),
)
def apply_mask(
    volume: str, mask: str, threshold: float, temporary_upsample: bool, output: str | None
) -> None:
    """Apply a binary mask to an OME-Zarr volume, resampled to match each resolution level."""
    volume_path = Path(volume)
    mask_path = Path(mask)
    output_path = Path(output) if output else None
    validate_output_path(output_path)

    if output_path is not None:
        shutil.copytree(volume_path, output_path)
        volume_path = output_path

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
        mask_da = nearest_upsample(mask_da)
    elif mask_da.shape > vol_arr.shape:
        click.echo("Downsampling mask by factor 2...")
        # The mask is a label array (binary, in this thresholded form) --
        # label_downsample() stays lazy/chunk-wise (see core/resample.py),
        # same as downsample/upsample's own label-aware paths.
        mask_da = label_downsample(mask_da)

    for scale_key, vol_z in volume_store.arrays():
        click.echo(f"Applying mask to scale {scale_key}...")
        vol_da = da.from_zarr(vol_z)

        if vol_da.shape != mask_da.shape:
            click.echo(f"Skipping {scale_key} (shape mismatch)")
            continue

        masked_da = vol_da * mask_da
        masked_da.to_zarr(vol_z, compute=True)

    click.echo("Mask application complete.")
