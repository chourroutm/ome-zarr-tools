from __future__ import annotations

import json
from pathlib import Path

import click
import zarr

from ome_zarr_tools.core.backup import backup_attrs, restore_attrs
from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.zarr_path import ZarrPathParamType
from ome_zarr_tools.io.ome_metadata import read_multiscales, validate


def _parse_tuple_input(value: str, length: int) -> tuple[float, ...]:
    parts = [p.strip() for p in value.replace(",", " ").split()]
    if len(parts) != length:
        raise ValueError(f"Expected {length} values, got {len(parts)}")
    return tuple(float(p) for p in parts)


def build_proposed_multiscales(
    name: str,
    spatial_unit: str,
    voxel_size: tuple[float, ...],
    axis_names: list[str],
    dataset_paths: list[str],
) -> list[dict]:
    """Build the proposed ``multiscales`` metadata from these field values.

    Pure function, extracted so both this command's own prompt flow and the
    TUI's diff/rich-view preview (tui/screens/metadata_screen.py) build the
    exact same proposed metadata from the exact same inputs -- no duplicated
    logic to drift out of sync.
    """
    return [
        {
            "version": "0.4",
            "name": name,
            "axes": [
                {"name": axis_names[0], "type": "space", "unit": spatial_unit},
                {"name": axis_names[1], "type": "space", "unit": spatial_unit},
                {"name": axis_names[2], "type": "space", "unit": spatial_unit},
            ],
            "datasets": [
                {
                    "path": dataset_path,
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [float(v) * (2**i) for v in voxel_size]},
                    ],
                }
                for i, dataset_path in enumerate(dataset_paths)
            ],
        }
    ]


def write_metadata(path: Path, group: zarr.Group, proposed_multiscales: list[dict]) -> Path:
    """Back up, write, and validate ``proposed_multiscales`` onto ``group``.

    Raises ``CliError`` (after restoring the backup) if the result doesn't
    validate. Extracted so the TUI's Run action (tui/screens/metadata_screen.py)
    can call this directly -- bypassing the interactive ``click.confirm`` below,
    which would otherwise block on stdin from a worker thread -- while the
    prompt-based command body keeps its own confirm step unchanged.
    """
    backup_path = backup_attrs(path, group)
    group.attrs["multiscales"] = proposed_multiscales
    is_valid, error = validate(group)
    if not is_valid:
        restore_attrs(group, backup_path)
        raise CliError(f"Validation failed; restored previous metadata. Details: {error}")
    return backup_path


@click.command(name="fix_metadata")
@click.argument("zarr_path", type=ZarrPathParamType(exists=True))
def fix_metadata(zarr_path: str) -> None:
    """Interactively populate/correct an OME-Zarr dataset's root metadata.

    Shows current metadata (if present), prompts for image name, voxel size,
    spatial unit, and axis names, then writes and validates updated metadata
    -- backing up the previous root attributes first.
    """
    path = Path(zarr_path)
    group = zarr.open_group(str(path), mode="r+")

    multiscales = read_multiscales(group)
    click.echo("\nCurrent multiscale metadata:")
    click.echo(json.dumps(multiscales, indent=2) if multiscales else "<none>")

    click.echo("\nEnter values (press Enter to keep the shown default).")

    default_name = multiscales[0].get("name") if multiscales else None
    name = click.prompt("Image name", default=default_name or "Image", show_default=True)

    default_unit = None
    if multiscales and multiscales[0].get("axes"):
        default_unit = multiscales[0]["axes"][0].get("unit")
    spatial_unit = click.prompt(
        "Spatial unit", default=default_unit or "micrometer", show_default=True
    )

    default_voxel = None
    if multiscales:
        datasets = multiscales[0].get("datasets", [])
        if datasets:
            for transform in datasets[0].get("coordinateTransformations", []):
                if transform.get("type") == "scale":
                    default_voxel = tuple(float(x) for x in transform["scale"])
                    break
    default_voxel_str = " ".join(str(f) for f in default_voxel) if default_voxel else "1.0 1.0 1.0"
    while True:
        try:
            voxel_size = _parse_tuple_input(
                click.prompt("Voxel size (z y x)", default=default_voxel_str, show_default=True),
                3,
            )
            break
        except ValueError as exc:
            click.echo(f"Invalid input: {exc}. Try again.")

    default_axes = ["z", "y", "x"]
    if multiscales and multiscales[0].get("axes"):
        default_axes = [
            axis.get("name", d)
            for axis, d in zip(multiscales[0]["axes"], default_axes, strict=False)
        ]
    axes_input = click.prompt("Axis names (space separated)", default=" ".join(default_axes))
    axis_names = [s.strip() for s in axes_input.replace(",", " ").split()][:3]
    if len(axis_names) != 3:
        click.echo("Warning: axis names length != 3, padding/truncating to 3 items.")
        axis_names = (axis_names + default_axes)[:3]

    dataset_paths = [d["path"] for d in multiscales[0]["datasets"]] if multiscales else ["0"]

    proposed_multiscales = build_proposed_multiscales(
        name, spatial_unit, voxel_size, axis_names, dataset_paths
    )

    click.echo("\nProposed metadata:")
    click.echo(json.dumps(proposed_multiscales, indent=2))

    if not click.confirm("Write this metadata to the OME-Zarr root attributes?"):
        click.echo("Aborted. No changes were written.")
        return

    backup_path = write_metadata(path, group, proposed_multiscales)
    click.echo(f"Backed up existing root attributes to {backup_path}")
    click.echo("Metadata successfully written and validated.")
