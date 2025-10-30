import click

@click.command()
@click.argument("zarr_path")
@click.argument("output_dir")
def extract(zarr_path, output_dir):
    """Extract images from ZARR_PATH to OUTPUT_DIR."""
    click.echo(f"Extracting images from {zarr_path} to {output_dir}")
    # TODO: Implement extraction logic
