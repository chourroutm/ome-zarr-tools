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


def _scale_of(dataset: dict[str, Any]) -> list[float]:
    scale_transform = next(t for t in dataset["coordinateTransformations"] if t["type"] == "scale")
    return list(scale_transform["scale"])


def add_half_pixel_translations(datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert a ``translation`` transform after each dataset's ``scale``, per axis:

        translation_N = (scale_N - scale_0) / 2

    The documented (non-normative -- a MUST/SHOULD isn't made of the value,
    only of translation coming after scale when present) convention for
    classical-binning downsampling, straight from the spec: "translations
    should be (pixel-size-at-resolution-N - pixel-size-at-resolution-0) / 2
    for correct multi-scale alignment" (ngff-spec index.md, § Multiscale
    coordinateTransformations). Anchors level 0 at translation 0 and aligns
    every coarser level to the same physical grid.
    """
    scale_0 = _scale_of(datasets[0])
    updated = []
    for dataset in datasets:
        transforms = [t for t in dataset["coordinateTransformations"] if t["type"] != "translation"]
        scale_n = _scale_of(dataset)
        translation = [(sn - s0) / 2 for sn, s0 in zip(scale_n, scale_0, strict=True)]
        transforms.append({"type": "translation", "translation": translation})
        updated.append({**dataset, "coordinateTransformations": transforms})
    return updated
