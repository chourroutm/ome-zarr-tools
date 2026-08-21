"""Top-level CLI entry point. Subcommands are registered by each command module."""

from __future__ import annotations

import click

from ome_zarr_tools.commands.apply_mask import apply_mask
from ome_zarr_tools.commands.config import config
from ome_zarr_tools.commands.downsample import downsample
from ome_zarr_tools.commands.extract import extract
from ome_zarr_tools.commands.fix_metadata import fix_metadata
from ome_zarr_tools.commands.from_images import from_images
from ome_zarr_tools.commands.inspect import inspect
from ome_zarr_tools.commands.interactive import interactive
from ome_zarr_tools.commands.migrate import migrate
from ome_zarr_tools.commands.upsample import upsample


@click.group()
@click.version_option(package_name="ome-zarr-tools")
def cli() -> None:
    """OME-Zarr Tools: work with OME-Zarr (OME-NGFF) multiscale datasets."""


cli.add_command(from_images)
cli.add_command(extract)
cli.add_command(fix_metadata)
cli.add_command(apply_mask)
cli.add_command(config)
cli.add_command(interactive)
cli.add_command(migrate)
cli.add_command(inspect)
cli.add_command(downsample)
cli.add_command(upsample)


if __name__ == "__main__":
    cli()
