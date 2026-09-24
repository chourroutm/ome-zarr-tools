"""The single source of truth mapping a configurable env-var name to the
``(command, option)`` pair(s) it feeds. Hand-written and explicit rather than
introspected from each command's options -- automatic introspection is
exactly what caused the pre-existing silent `extract`/`inspect`
`output_format` name collision in the old TUI's `collect_default_values()`
(research.md §5).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurableVariable:
    name: str
    targets: tuple[tuple[str, str], ...]


CONFIGURABLE_VARIABLES: list[ConfigurableVariable] = [
    ConfigurableVariable(
        "OME_ZARR_TOOLS_FROM_IMAGES_VOXEL_SIZE_UNIT",
        (("from_images", "voxel_size_unit"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_FROM_IMAGES_NUM_LEVELS",
        (("from_images", "num_levels"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE",
        (("from_images", "chunk_size"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_TARGET_VERSION",
        (("from_images", "target_version"), ("migrate", "target_version")),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_CHUNKS_PER_SHARD",
        (("from_images", "chunks_per_shard"), ("migrate", "chunks_per_shard")),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_EXTRACT_LEVEL",
        (("extract", "level"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_EXTRACT_OUTPUT_FORMAT",
        (("extract", "output_format"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD",
        (("apply_mask", "threshold"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_INSPECT_JSON",
        (("inspect", "as_json"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS",
        (("downsample", "num_levels"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_DOWNSAMPLE_LABEL",
        (("downsample", "label"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_UPSAMPLE_NUM_LEVELS",
        (("upsample", "num_levels"),),
    ),
    ConfigurableVariable(
        "OME_ZARR_TOOLS_UPSAMPLE_SMOOTH",
        (("upsample", "smooth"),),
    ),
]

_BY_NAME: dict[str, ConfigurableVariable] = {v.name: v for v in CONFIGURABLE_VARIABLES}

_UNRECOGNIZED_PREFIX = "OME_ZARR_TOOLS_"


def build_default_map(values: dict[str, str]) -> dict[str, dict[str, str]]:
    """Nest ``values`` by ``(command, option)`` target, for use as a ``click``
    ``default_map``. Unrecognized keys are silently skipped here -- reporting
    them is ``unrecognized_keys()``'s job, called separately by each caller."""
    mapping: dict[str, dict[str, str]] = {}
    for name, raw_value in values.items():
        variable = _BY_NAME.get(name)
        if variable is None:
            continue
        for command, option in variable.targets:
            mapping.setdefault(command, {})[option] = raw_value
    return mapping


def unrecognized_keys(values: dict[str, str]) -> list[str]:
    """Every key in ``values`` that looks like it was meant for this tool
    (``OME_ZARR_TOOLS_``-prefixed) but doesn't match any known variable.
    Non-prefixed keys are never included -- a file may legitimately hold
    unrelated variables (e.g. cloud credentials)."""
    return [
        name for name in values if name.startswith(_UNRECOGNIZED_PREFIX) and name not in _BY_NAME
    ]
