import click
from ome_zarr_tools.from_images import from_images
from ome_zarr_tools.extract import extract
from ome_zarr_tools.fix_metadata import fix_metadata
from ome_zarr_tools.apply_mask import apply_mask
from ome_zarr_tools.config import config

@click.group()
def cli():
    """OME-Zarr Tools CLI."""
    pass

cli.add_command(from_images)
cli.add_command(extract)
cli.add_command(fix_metadata)
cli.add_command(apply_mask)
cli.add_command(config)

if __name__ == "__main__":
    cli()
