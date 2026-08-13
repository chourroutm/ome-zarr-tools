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


def validate_chunks_per_shard(target_version: str, chunks_per_shard: int | None) -> None:
    """Raise ``CliError`` if ``chunks_per_shard`` is set for a pre-0.5 target version.

    Sharding is a Zarr v3 storage feature (OME-NGFF 0.5+); Zarr v2 (0.4) has no
    concept of shards. ``ngff_zarr`` itself already rejects this combination, but
    only once conversion actually starts -- this raises immediately, before any
    zarr I/O, backup, or (on the CLI) the confirmation prompt. Shared by the CLI
    command and the TUI's Form screen (``tui/screens/metadata_screen.py``), which
    bypasses the CLI command entirely.
    """
    if chunks_per_shard is not None and target_version == DEFAULT_TARGET_VERSION:
        raise CliError(
            "--chunks_per_shard requires --target_version 0.5 or later "
            f"-- sharding isn't supported by Zarr v2 (target version {target_version!r})."
        )


def validate_output_path(output_path: Path | None) -> None:
    """Raise ``CliError`` if ``output_path`` is given and already exists.

    A fresh output location is always created new -- overwriting an existing
    path silently (as ``ngff_zarr`` would do on its own) risks destroying
    whatever was already there. Shared by the CLI command and the TUI's Form
    screen, same reasoning as ``validate_chunks_per_shard``.
    """
    if output_path is not None and output_path.exists():
        raise CliError(f"{output_path} already exists; choose a new path or remove it first.")


def _convert_and_validate(
    source_path: Path, dest_path: Path, target_version: str, chunks_per_shard: int | None
) -> None:
    """Convert ``source_path`` to ``dest_path`` via ``ngff_zarr`` and validate the
    result, raising ``CliError`` (and removing ``dest_path``) on any failure.
    Shared by both ``apply_migration()`` branches below (in-place and to a new
    output path) -- the conversion/validate/cleanup steps are identical either
    way, only the eventual destination differs.
    """
    try:
        import ngff_zarr as nz
    except ImportError as exc:
        raise CliError(f"ngff-zarr is not installed: {exc}") from exc

    try:
        multiscales = nz.from_ngff_zarr(str(source_path), validate=False)
        nz.to_ngff_zarr(
            str(dest_path),
            multiscales,
            version=target_version,
            use_tensorstore=False,
            chunks_per_shard=chunks_per_shard,
        )
    except Exception as exc:
        if dest_path.exists():
            shutil.rmtree(dest_path)
        raise CliError(f"Migration failed; nothing written to {dest_path}. Details: {exc}") from exc

    new_group = zarr.open_group(str(dest_path), mode="r")
    is_valid, error = validate(new_group)
    if not is_valid:
        shutil.rmtree(dest_path)
        raise CliError(
            f"Migrated dataset failed validation; nothing left at {dest_path}. Details: {error}"
        )


def preview_migration(path: Path, target_version: str, chunks_per_shard: int | None = None) -> dict:
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
    nz.to_ngff_zarr(
        store,
        multiscales,
        version=target_version,
        use_tensorstore=False,
        chunks_per_shard=chunks_per_shard,
    )
    preview_group = zarr.open_group(store, mode="r")
    return dict(preview_group.attrs)


def apply_migration(
    path: Path,
    group: zarr.Group,
    target_version: str,
    chunks_per_shard: int | None = None,
    output_path: Path | None = None,
) -> Path:
    """Convert ``path`` to ``target_version``, either in place (back up, convert
    to a temp dir, swap) or -- when ``output_path`` is given -- to that new
    location, leaving ``path`` completely untouched (no backup needed, since
    nothing at ``path`` is modified).

    Raises ``CliError`` on failure, leaving ``path`` untouched either way.
    Returns the backup path (in-place) or ``output_path`` (new location).
    Extracted so the TUI's Run action (tui/screens/metadata_screen.py) can call
    this directly -- bypassing the interactive ``click.confirm`` below, which
    would otherwise block on stdin from a worker thread -- while the CLI
    command keeps its own detect/confirm flow unchanged.
    """
    if output_path is not None:
        validate_output_path(output_path)
        _convert_and_validate(path, output_path, target_version, chunks_per_shard)
        return output_path

    backup_path = backup_attrs(path, group)

    tmp_path = path.parent / f"{path.name}.migrating"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)

    _convert_and_validate(path, tmp_path, target_version, chunks_per_shard)

    shutil.rmtree(path)
    tmp_path.rename(path)
    return backup_path


@click.command(name="migrate")
@click.argument("zarr_path", type=ZarrPathParamType(exists=True, file_okay=False))
@click.option(
    "--target_version",
    default=DEFAULT_TARGET_VERSION,
    show_default=True,
    help=(
        "Target OME-NGFF specification version. Implies the Zarr storage format "
        "(0.4 -> Zarr v2, 0.5+ -> Zarr v3) -- not independently selectable."
    ),
)
@click.option(
    "--chunks_per_shard",
    type=int,
    default=None,
    help=(
        "Chunks per shard, per axis (isotropic). Requires --target_version 0.5 "
        "or later -- Zarr v2 (0.4) has no concept of shards. Omit for no sharding."
    ),
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Write the migrated dataset to this new path instead of converting "
        "ZARR_PATH in place; ZARR_PATH is left completely untouched. Must not "
        "already exist. Omit to migrate ZARR_PATH in place (default)."
    ),
)
def migrate(
    zarr_path: str, target_version: str, chunks_per_shard: int | None, output: str | None
) -> None:
    """Upgrade ZARR_PATH's OME-NGFF specification version (metadata and storage format together)."""
    validate_chunks_per_shard(target_version, chunks_per_shard)
    output_path = Path(output) if output else None
    validate_output_path(output_path)
    path = Path(zarr_path)
    group = zarr.open_group(str(path), mode="r")
    source_version = detect_version(group)
    if source_version is None:
        raise CliError(f"Could not detect an OME-NGFF specification version for {zarr_path}.")

    if output_path is None and source_version == target_version:
        click.echo(f"{zarr_path} is already at version {target_version}; nothing to do.")
        return

    click.echo(f"Source version: {source_version}")
    click.echo(f"Target version: {target_version}")
    if output_path is not None:
        prompt = f"Write {zarr_path} (migrated to {target_version}) to {output}?"
    else:
        prompt = f"Migrate {zarr_path} from {source_version} to {target_version}?"
    if not click.confirm(prompt):
        click.echo("Aborted. No changes were written.")
        return

    result_path = apply_migration(path, group, target_version, chunks_per_shard, output_path)
    if output_path is not None:
        click.echo(f"Migrated {zarr_path} to {result_path}.")
    else:
        click.echo(f"Backed up existing root attributes to {result_path}")
        click.echo(f"Migrated {zarr_path} from {source_version} to {target_version}.")
