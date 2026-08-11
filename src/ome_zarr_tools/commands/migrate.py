from __future__ import annotations

import shutil
from pathlib import Path

import click
import zarr

from ome_zarr_tools.core.backup import backup_attrs
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.zarr_path import ZarrPathParamType
from ome_zarr_tools.io.ome_metadata import detect_version, validate

DEFAULT_TARGET_VERSION = "0.4"


def preview_migration(path: Path, target_version: str) -> dict:
    """Return the root attrs a migration to ``target_version`` would produce, without writing.

    Calls the same ``ngff_zarr`` conversion the real command uses, but targets an
    in-memory ``zarr.storage.MemoryStore`` instead of the real temp-then-swap path
    -- zero filesystem I/O, nothing to clean up (research.md, verified). Used by
    the TUI's Confirm screen (tui/screens/metadata_screen.py) to show the
    side-by-side diff before applying; the real command below is unmodified by
    this -- Confirm still invokes it normally.
    """
    try:
        import ngff_zarr as nz
    except ImportError as exc:
        raise CliError(f"ngff-zarr is not installed: {exc}") from exc

    multiscales = nz.from_ngff_zarr(str(path), validate=False)
    store = zarr.storage.MemoryStore()
    nz.to_ngff_zarr(store, multiscales, version=target_version, use_tensorstore=False)
    preview_group = zarr.open_group(store, mode="r")
    return dict(preview_group.attrs)


def apply_migration(path: Path, group: zarr.Group, target_version: str) -> Path:
    """Back up, convert (real temp-then-swap write), and validate ``path`` to ``target_version``.

    Raises ``CliError`` (leaving the original dataset untouched) on failure.
    Extracted so the TUI's Run action (tui/screens/metadata_screen.py) can call
    this directly -- bypassing the interactive ``click.confirm`` below, which
    would otherwise block on stdin from a worker thread -- while the CLI
    command keeps its own detect/confirm flow unchanged.
    """
    backup_path = backup_attrs(path, group)

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
    return backup_path


@click.command(name="migrate")
@click.argument("zarr_path", type=ZarrPathParamType(exists=True))
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

    backup_path = apply_migration(path, group, target_version)
    click.echo(f"Backed up existing root attributes to {backup_path}")
    click.echo(f"Migrated {zarr_path} from {source_version} to {target_version}.")
