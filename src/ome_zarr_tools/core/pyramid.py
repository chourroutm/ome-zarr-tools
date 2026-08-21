"""Shared "add new multiscale levels" logic for ``downsample``/``upsample``.

Unlike ``migrate`` (which rewrites a dataset's *entire* pyramid to convert its
storage format), these commands only ever *add* new levels -- existing levels'
on-disk arrays are never rewritten, moved, or renamed. That makes the safety
story simpler than ``migrate``'s temp-then-swap dance: new arrays are written
first (harmless -- nothing references them yet), the dataset's root attrs are
backed up, the extended ``multiscales`` metadata is written and validated, and
on any failure the new arrays are removed and the attrs restored (see
research.md § "In-place safety").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import dask.array as da
import zarr
from dask.array.core import Array as DaskArray

from ome_zarr_tools.core.backup import backup_attrs, restore_attrs
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.io.ome_metadata import (
    add_half_pixel_translations,
    read_multiscales,
    validate,
    write_multiscales,
)


@dataclass
class NewLevel:
    """One new multiscale level to add: its future array path, pixel data,
    the chunk shape to store it with, and its resolution (``scale``, one
    value per axis -- ``translation`` is deliberately not part of this: it
    depends on which entry ends up at ``datasets[0]`` *after* this level is
    added, which ``commit_new_levels()`` alone knows how to compute for the
    whole list, not any single new level in isolation)."""

    path: str
    array: DaskArray | Any
    chunks: tuple[int, ...]
    scale: list[float]


def next_new_paths(existing_datasets: list[dict[str, Any]], n: int) -> list[str]:
    """Return ``n`` fresh ``path`` strings that don't collide with any of
    ``existing_datasets``'s own paths -- continuing past the highest existing
    integer-parseable path (or starting at ``"0"`` if none parse as an int).
    Per the OME-NGFF spec, ``path`` is an arbitrary string identifier with no
    ordering meaning of its own (research.md), so these new paths carry no
    claim about where the new levels sit in the ``datasets`` list -- that's
    ``commit_new_levels()``'s ``position`` argument, entirely separate.
    """
    used = {d["path"] for d in existing_datasets}
    next_int = 0
    for dataset in existing_datasets:
        try:
            next_int = max(next_int, int(dataset["path"]) + 1)
        except (ValueError, TypeError):
            continue

    new_paths: list[str] = []
    candidate = next_int
    while len(new_paths) < n:
        candidate_str = str(candidate)
        if candidate_str not in used:
            new_paths.append(candidate_str)
            used.add(candidate_str)
        candidate += 1
    return new_paths


def _remove_arrays(group: zarr.Group, paths: list[str]) -> None:
    for path in paths:
        if path in group:
            del group[path]


def commit_new_levels(
    path: Path,
    group: zarr.Group,
    new_levels: list[NewLevel],
    position: Literal["append", "prepend"],
) -> None:
    """Write ``new_levels``'s arrays into ``group`` and extend its
    ``multiscales[0].datasets`` list (``position="append"`` puts them after
    the existing entries, ``"prepend"`` puts them before). Validates the
    result; on any failure, removes the newly written arrays and -- if the
    metadata had already been updated -- restores it from a backup taken
    just before. Raises ``CliError`` on failure, leaving ``group`` exactly as
    it was before this call either way.
    """
    written_paths: list[str] = []
    try:
        for level in new_levels:
            target = group.create_array(
                level.path, shape=level.array.shape, dtype=level.array.dtype, chunks=level.chunks
            )
            # dask's stubs don't recognize a zarr.Array as a valid store target,
            # though it is one at runtime (this is the documented way to write a
            # dask array into a specific array within an already-open zarr group).
            da.store(da.asarray(level.array), target)  # type: ignore[arg-type]
            written_paths.append(level.path)
    except Exception as exc:
        _remove_arrays(group, written_paths)
        raise CliError(f"Adding levels failed; nothing written to {path}. Details: {exc}") from exc

    backup_path = backup_attrs(path, group)
    try:
        multiscales = read_multiscales(group)
        if not multiscales:
            raise CliError(f"No multiscales metadata found in {path}.")
        existing_datasets = multiscales[0]["datasets"]
        new_entries = [
            {
                "path": level.path,
                "coordinateTransformations": [{"type": "scale", "scale": level.scale}],
            }
            for level in new_levels
        ]
        if position == "append":
            updated_datasets = existing_datasets + new_entries
        else:
            updated_datasets = new_entries + existing_datasets
        # Recomputed for the *whole* list, not just the new entries: translation is
        # anchored to whichever dataset ends up at position 0 (data-model.md), and
        # `upsample`'s prepend changes that -- every existing entry's translation
        # (previously anchored to the old datasets[0]) would otherwise go stale.
        multiscales[0]["datasets"] = add_half_pixel_translations(updated_datasets)
        write_multiscales(group, multiscales)

        is_valid, error = validate(group)
        if not is_valid:
            raise CliError(
                f"Adding levels failed validation; nothing left at {path}. Details: {error}"
            )
    except Exception as exc:
        restore_attrs(group, backup_path)
        _remove_arrays(group, written_paths)
        if isinstance(exc, CliError):
            raise
        raise CliError(f"Adding levels failed; nothing left at {path}. Details: {exc}") from exc
