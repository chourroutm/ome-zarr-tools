from __future__ import annotations

import shutil
from pathlib import Path

import click
import zarr

from ome_zarr_tools.core.backup import backup_attrs
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.io.ome_metadata import detect_version, validate

DEFAULT_TARGET_VERSION = "0.4"


@click.command(name="migrate")
@click.argument("zarr_path", type=click.Path(exists=True))
@click.option(
    "--target_version",
    default=DEFAULT_TARGET_VERSION,
    show_default=True,
    help=(
        "Target OME-NGFF specification version. Implies the Zarr storage format "
        "(0.4 -> Zarr v2, 0.5+ -> Zarr v3) -- not independently selectable."
    ),
)
def migrate(zarr_path: str, target_version: str) -> None:
    """Upgrade ZARR_PATH's OME-NGFF specification version (metadata and storage format together)."""
    path = Path(zarr_path)
    group = zarr.open_group(str(path), mode="r")
    source_version = detect_version(group)
    if source_version is None:
        raise CliError(f"Could not detect an OME-NGFF specification version for {zarr_path}.")

    if source_version == target_version:
        click.echo(f"{zarr_path} is already at version {target_version}; nothing to do.")
        return

    click.echo(f"Source version: {source_version}")
    click.echo(f"Target version: {target_version}")
    if not click.confirm(f"Migrate {zarr_path} from {source_version} to {target_version}?"):
        click.echo("Aborted. No changes were written.")
        return

    backup_path = backup_attrs(path, group)
    click.echo(f"Backed up existing root attributes to {backup_path}")

    try:
        import ngff_zarr as nz
    except ImportError as exc:
        raise CliError(f"ngff-zarr is not installed: {exc}") from exc

    tmp_path = path.parent / f"{path.name}.migrating"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)

    try:
        multiscales = nz.from_ngff_zarr(str(path), validate=False)
        nz.to_ngff_zarr(str(tmp_path), multiscales, version=target_version, use_tensorstore=False)
    except Exception as exc:
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        raise CliError(
            f"Migration failed; original dataset left untouched. Details: {exc}"
        ) from exc

    new_group = zarr.open_group(str(tmp_path), mode="r")
    is_valid, error = validate(new_group)
    if not is_valid:
        shutil.rmtree(tmp_path)
        raise CliError(
            f"Migrated dataset failed validation; original left untouched. Details: {error}"
        )

    shutil.rmtree(path)
    tmp_path.rename(path)

    click.echo(f"Migrated {zarr_path} from {source_version} to {target_version}.")
