"""Shared OME metadata read/validate helpers, used by ``fix_metadata``, ``migrate``, ``inspect``.

data-model.md § OME-Zarr Dataset: ``metadata_version`` is read from
``attrs["ome"]["version"]`` (0.5+) or the legacy top-level ``attrs["multiscales"]``
(0.4 and earlier).
"""

from __future__ import annotations

from typing import Any

import zarr
from ome_zarr_models import open_ome_zarr


def read_multiscales(group: zarr.Group) -> list[dict[str, Any]] | None:
    """Return the raw ``multiscales`` metadata list, or ``None`` if absent."""
    ome = group.attrs.get("ome")
    if isinstance(ome, dict) and isinstance(ome.get("multiscales"), list):
        return ome["multiscales"]
    multiscales = group.attrs.get("multiscales")
    return multiscales if isinstance(multiscales, list) else None


def detect_version(group: zarr.Group) -> str | None:
    """Return the dataset's OME-NGFF specification version, or ``None`` if undetectable."""
    try:
        return str(open_ome_zarr(group).ome_zarr_version)
    except Exception:
        pass
    multiscales = read_multiscales(group)
    if not multiscales:
        return None
    version = multiscales[0].get("version")
    return str(version) if version is not None else None


def validate(group: zarr.Group) -> tuple[bool, str | None]:
    """Validate a dataset's OME metadata. Returns ``(is_valid, error_message)``."""
    try:
        open_ome_zarr(group)
    except Exception as exc:
        return False, str(exc)
    return True, None
