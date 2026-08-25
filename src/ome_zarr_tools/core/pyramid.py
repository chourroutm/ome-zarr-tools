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


def next_new_paths(
    existing_datasets: list[dict[str, Any]], n: int, group: zarr.Group | None = None
) -> list[str]:
    """Return ``n`` fresh ``path`` strings that don't collide with any of
    ``existing_datasets``'s own paths, or -- when ``group`` is given -- any
    array/group member actually present on disk (e.g. a stray array left
    behind by an interrupted prior run, never recorded in ``datasets``, that
    would otherwise make the coming ``group.create_array()`` fail with "an
    array already exists at path ..."). Continues past the highest existing
    integer-parseable path (or starts at ``"0"`` if none parse as an int).
    Per the OME-NGFF spec, ``path`` is an arbitrary string identifier with no
    ordering meaning of its own (research.md), so these new paths carry no
    claim about where the new levels sit in the ``datasets`` list -- that's
    ``commit_new_levels()``'s ``position`` argument, entirely separate.
    """
    used = {d["path"] for d in existing_datasets}
    if group is not None:
        used |= set(group.array_keys()) | set(group.group_keys())
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
    """Delete each of ``paths`` from ``group``, tolerating paths that don't
    actually exist there. Deliberately does *not* guard with ``if path in
    group`` first: a group opened with (auto-detected) consolidated metadata
    reports membership from that cached listing, which a just-created array
    isn't reflected in until the group is explicitly re-consolidated -- so
    that guard would silently skip deleting an array this same call just
    wrote, leaving it orphaned on disk for a future run to collide with.
    """
    for path in paths:
        try:
            del group[path]
        except KeyError:
            pass


def _next_unused_int_path(used: set[str], start: int) -> tuple[str, int]:
    """Return the first ``str(candidate)`` (``candidate >= start``) not in
    ``used``, and ``candidate + 1`` (so callers can pass it back in as the
    next call's ``start``)."""
    candidate = start
    while str(candidate) in used:
        candidate += 1
    return str(candidate), candidate + 1


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
    multiscales = read_multiscales(group)
    if not multiscales:
        raise CliError(f"No multiscales metadata found in {path}.")
    # Zarr v3 (OME-NGFF 0.5+) arrays carry their own per-axis dimension_names,
    # which ome_zarr_models' validation requires -- read_multiscales's own
    # dual-shape support means multiscales[0]["axes"] is available regardless
    # of which of the two attrs shapes this dataset uses. Zarr v2 (0.4) has no
    # such concept and raises if passed one at all, so this is None there.
    dimension_names = (
        [axis["name"] for axis in multiscales[0]["axes"]]
        if group.metadata.zarr_format == 3
        else None
    )

    # Seeds next_int / used for the collision-retry below: existing_datasets'
    # own paths, plus every path already claimed by an earlier level in this
    # same batch (next_new_paths() already steered new_levels away from these,
    # but a group opened with stale consolidated metadata can still make
    # create_array() below hit a real collision it didn't know to avoid).
    used_paths = {d["path"] for d in multiscales[0]["datasets"]}
    next_candidate = 0
    for used_path in used_paths:
        try:
            next_candidate = max(next_candidate, int(used_path) + 1)
        except (ValueError, TypeError):
            continue

    written_paths: list[str] = []
    try:
        for level in new_levels:
            while True:
                try:
                    target = group.create_array(
                        level.path,
                        shape=level.array.shape,
                        dtype=level.array.dtype,
                        chunks=level.chunks,
                        dimension_names=dimension_names,
                    )
                    break
                except (zarr.errors.ContainsArrayError, zarr.errors.ContainsGroupError):
                    # A stray array/group from an earlier interrupted run, invisible
                    # to next_new_paths()'s own collision check (see _remove_arrays'
                    # docstring) -- claim the next integer path instead of failing.
                    used_paths.add(level.path)
                    level.path, next_candidate = _next_unused_int_path(used_paths, next_candidate)
            # dask's stubs don't recognize a zarr.Array as a valid store target,
            # though it is one at runtime (this is the documented way to write a
            # dask array into a specific array within an already-open zarr group).
            da.store(da.asarray(level.array), target)  # type: ignore[arg-type]
            written_paths.append(level.path)
            used_paths.add(level.path)
    except Exception as exc:
        _remove_arrays(group, written_paths)
        raise CliError(f"Adding levels failed; nothing written to {path}. Details: {exc}") from exc

    backup_path = backup_attrs(path, group)
    try:
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
