"""Metadata backup-before-write helper (FR-005, data-model.md § Metadata Backup)."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

import zarr


def backup_attrs(path: Path, group: zarr.Group) -> Path:
    """Snapshot ``group.attrs`` to a timestamped JSON file next to ``path``; return its path."""
    attrs_snapshot = dict(group.attrs)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.parent / f"{path.name}_zattrs_backup_{timestamp}.json"
    backup_path.write_text(json.dumps(attrs_snapshot, indent=2))
    return backup_path


def restore_attrs(group: zarr.Group, backup_path: Path) -> None:
    """Restore ``group.attrs`` from a snapshot written by :func:`backup_attrs`."""
    attrs_snapshot: dict[str, Any] = json.loads(backup_path.read_text())
    for key in list(group.attrs):
        del group.attrs[key]
    for key, value in attrs_snapshot.items():
        group.attrs[key] = value
