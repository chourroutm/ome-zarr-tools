"""Top-level CLI entry point. Subcommands are registered by each command module."""

from __future__ import annotations

from pathlib import Path

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
from ome_zarr_tools.core.config_registry import build_default_map, unrecognized_keys
from ome_zarr_tools.core.env_file import read_env_file


@click.group()
@click.version_option(package_name="ome-zarr-tools")
@click.option(
    "--env-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help=(
        "Env-var file (see `config`) supplying default option values for the "
        "subcommand run. An explicitly passed flag always overrides it."
    ),
)
@click.pass_context
def cli(ctx: click.Context, env_file: str | None) -> None:
    """OME-Zarr Tools: work with OME-Zarr (OME-NGFF) multiscale datasets."""
    ctx.ensure_object(dict)
    if env_file is None:
        return
    values, dup_warnings = read_env_file(Path(env_file))
    for warning in dup_warnings:
        click.echo(f"Warning: {warning}", err=True)
    names = unrecognized_keys(values)
    for name in names:
        click.echo(f"Warning: unrecognized key {name!r} in {env_file}.", err=True)
    ctx.default_map = build_default_map(values)
    ctx.obj["unrecognized"] = names
    ctx.obj["env_file"] = env_file


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
