from __future__ import annotations

from pathlib import Path

import click

from ome_zarr_tools.core.config_registry import unrecognized_keys
from ome_zarr_tools.core.env_file import is_valid_env_key, read_env_file, write_env_file
from ome_zarr_tools.core.errors import CliError


def _report_existing_content(path: Path) -> dict[str, str]:
    """Read ``path``'s current content (empty dict if it doesn't exist yet),
    printing its duplicate-key warnings and unrecognized-key errors (FR-015/
    FR-016, error-level -- this is a `config` subcommand)."""
    if not path.exists():
        return {}
    values, dup_warnings = read_env_file(path)
    for warning in dup_warnings:
        click.echo(f"Warning: {warning}", err=True)
    for name in unrecognized_keys(values):
        click.echo(f"Error: unrecognized key {name!r} in {path}.", err=True)
    return values


@click.group()
def config() -> None:
    """Manage an env-var settings file for ome-zarr-tools.

    Each subcommand takes a required ENV_FILE path. Apply a file's values to
    a real command run with the top-level `--env-file` option, e.g.
    `ome-zarr-tools --env-file settings.env from_images ...`.
    """


@config.command("show")
@click.argument("env_file", type=click.Path(dir_okay=False))
def show(env_file: str) -> None:
    """Show the contents of ENV_FILE."""
    path = Path(env_file)
    values, dup_warnings = read_env_file(path)
    for warning in dup_warnings:
        click.echo(f"Warning: {warning}", err=True)
    for name in unrecognized_keys(values):
        click.echo(f"Error: unrecognized key {name!r} in {path}.", err=True)

    if not values:
        click.echo("<empty>")
        return
    for key, value in values.items():
        click.echo(f"{key}={value}")


@config.command("set")
@click.argument("env_file", type=click.Path(dir_okay=False))
@click.argument("pairs", nargs=-1, required=True)
def set_config(env_file: str, pairs: tuple[str, ...]) -> None:
    """Set one or more KEY=VALUE pairs in ENV_FILE, creating it if needed.

    Example: ome-zarr-tools config set settings.env OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=128
    """
    parsed: list[tuple[str, str]] = []
    for pair in pairs:
        if "=" not in pair:
            raise CliError(f"Expected KEY=VALUE, got: {pair!r}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not is_valid_env_key(key):
            raise CliError(f"Invalid key {key!r}: must match ^[A-Za-z_][A-Za-z0-9_]*$.")
        parsed.append((key, value.strip()))

    path = Path(env_file)
    values = _report_existing_content(path)
    for key, value in parsed:
        values[key] = value
        click.echo(f"Set {key}={value} in {path}")
    write_env_file(path, values)
    click.echo(f"Wrote {path}")


@config.command("reset")
@click.argument("env_file", type=click.Path(dir_okay=False))
@click.option("--all", "remove_all", is_flag=True, help="Remove the entire file.")
@click.argument("keys", nargs=-1, required=False)
def reset_config(env_file: str, remove_all: bool, keys: tuple[str, ...]) -> None:
    """Remove one or more KEYS from ENV_FILE, or the whole file with --all."""
    if remove_all and keys:
        raise CliError("Pass either one or more KEYs or --all, not both.")
    if not remove_all and not keys:
        raise CliError("Provide one or more keys to reset, or use --all to remove the file.")

    path = Path(env_file)
    if not path.exists():
        raise CliError(f"{path} does not exist.")

    if remove_all:
        path.unlink()
        click.echo(f"Removed {path}")
        return

    values, dup_warnings = read_env_file(path)
    for warning in dup_warnings:
        click.echo(f"Warning: {warning}", err=True)
    for name in unrecognized_keys(values):
        click.echo(f"Error: unrecognized key {name!r} in {path}.", err=True)

    removed = [k for k in keys if k in values]
    for k in removed:
        values.pop(k, None)
    write_env_file(path, values)
    click.echo(f"Removed keys {removed} from {path}")
