import json
import datetime
from pathlib import Path

import click
import zarr

try:
    import ome_zarr_models.v04 as ome_models
except Exception:  # pragma: no cover - optional dependency
    ome_models = None


def _parse_tuple_input(value: str, length: int) -> tuple[float, ...]:
    parts = [p.strip() for p in value.replace(",", " ").split()]
    if len(parts) != length:
        raise ValueError(f"Expected {length} values, got {len(parts)}")
    return tuple(float(p) for p in parts)


@click.command()
@click.argument("zarr_path", type=click.Path(exists=True))
def fix_metadata(zarr_path: str):
    """
    Point to an OME-Zarr and start an interactive session to populate (or fix)
    the OME-Zarr metadata fields.

    This command:
      - Makes a JSON backup of existing root attributes (saved next to the Zarr store)
      - Presents current metadata (if present)
      - Prompts interactively for key fields (image name, voxel size, units, axis names)
      - Writes updated ome metadata (v0.5-style) and validates it with ome-zarr-models (if available)

    Arguments:
      ZARR_PATH: path to an existing .ome.zarr directory or any zarr group on disk.

    Dependencies:
      - zarr
      - ome-zarr-models (optional but recommended) (package providing ome_zarr_models.v05)
    """
    zarr_path = Path(zarr_path)
    group = zarr.open_group(zarr_path, mode="r+")

    # Backup existing root attributes
    attrs = dict(group.attrs.asdict())
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = zarr_path.parent / f"{zarr_path.name}_zattrs_backup_{ts}.json"
    with backup_path.open("w") as f:
        json.dump(attrs, f, indent=2)
    click.echo(f"Backed up root attributes to {backup_path}")

    # Show current ome metadata if present
    existing_ome = attrs.get("ome") or None
    if isinstance(existing_ome, dict):
        existing_multiscales = existing_ome.get("multiscales")
    else:
        existing_multiscales = attrs.get("multiscales") or {}

    click.echo("\nCurrent OME metadata (root 'ome' attribute):")
    if existing_ome:
        click.echo(json.dumps(existing_ome, indent=2))
    else:
        click.echo("<no 'ome' attribute present>")
    
    click.echo("\nCurrent multiscale metadata (root 'multiscales' attribute):")
    if existing_multiscales:
        click.echo(json.dumps(existing_multiscales, indent=2))
    else:
        click.echo("<no 'multiscales' attribute present>")

    # Interactive prompts
    click.echo("\nEnter values (press Enter to keep shown default / current value).")

    # Image name
    default_name = None
    if existing_multiscales and isinstance(existing_multiscales, list):
        default_name = existing_multiscales[0].get("name")
    name = click.prompt("Image name", default=default_name or "image", show_default=True)

    # Spatial unit
    default_unit = None
    if existing_multiscales and existing_multiscales[0].get("axes"):
        axes = existing_multiscales[0]["axes"]
        if len(axes) >= 1:
            default_unit = axes[0].get("unit")
    spatial_unit = click.prompt("Spatial unit", default=default_unit or "micrometer", show_default=True)

    # Voxel size (3 floats)
    default_voxel = None
    if existing_multiscales:
        ds = existing_multiscales[0].get("datasets", [])
        if ds and ds[0].get("coordinateTransformations"):
            for ct in ds[0]["coordinateTransformations"]:
                if ct.get("type") == "scale":
                    default_voxel = tuple(float(x) for x in ct.get("scale", []))
                    break
    default_voxel_str = " ".join(str(f) for f in default_voxel) if default_voxel else "1.0 1.0 1.0"
    while True:
        try:
            voxel_input = click.prompt("Voxel size (x y z)", default=default_voxel_str, show_default=True)
            voxel_size = _parse_tuple_input(voxel_input, 3)
            break
        except ValueError as e:
            click.echo(f"Invalid input: {e}. Try again.")

    # Axis order / names (comma-separated)
    default_axes = ["x", "y", "z"]
    if existing_multiscales and existing_multiscales[0].get("axes"):
        default_axes = [a.get("name", d) for a, d in zip(existing_multiscales[0]["axes"], default_axes)]
    axes_input = click.prompt("Axis names (comma or space separated, e.g. x y z)", default=" ".join(default_axes))
    axis_names = [s.strip() for s in axes_input.replace(",", " ").split()][:3]
    if len(axis_names) != 3:
        click.echo("Warning: axis names length != 3, padding/truncating to 3 items.")
        axis_names = (axis_names + default_axes)[:3]

    # Confirm changes
    click.echo("\nProposed metadata summary:")
    proposed = {
        "version": "0.4",
        "multiscales": [
            {
                "name": name,
                "type": "local mean",
                "metadata": {
                    "description": "Metadata populated/edited with ome-zarr-tools fix_metadata.",
                },
                "axes": [
                    {"name": axis_names[0], "type": "space", "unit": spatial_unit},
                    {"name": axis_names[1], "type": "space", "unit": spatial_unit},
                    {"name": axis_names[2], "type": "space", "unit": spatial_unit},
                ],
                "datasets": [
                    {
                        "path": "0",
                        "coordinateTransformations": [
                            {"type": "scale", "scale": [float(v) for v in voxel_size]},
                            {"type": "translation", "translation": [(float(v) / 2.0) for v in voxel_size]},
                        ],
                    }
                ],
            }
        ],
    }
    click.echo(json.dumps(proposed, indent=2))

    if not click.confirm("Write these metadata to the OME-Zarr root attributes?"):
        click.echo("Aborted. No changes were written.")
        return

    # Write metadata
    group.attrs["ome"] = proposed
    # also write top-level 'multiscales' for compatibility with tools expecting it
    group.attrs["multiscales"] = proposed["multiscales"]

    # Validate using ome-zarr-models if available
    if ome_models is not None:
        try:
            ome_models.Image.from_zarr(group)
            click.echo("Validation with ome-zarr-models succeeded.")
        except Exception as exc:
            # restore backup if validation fails
            with backup_path.open() as f:
                backup_attrs = json.load(f)
            # restore root attributes
            for k in list(group.attrs):
                del group.attrs[k]
            for k, v in backup_attrs.items():
                group.attrs[k] = v
            click.echo("Validation failed. Restored previous root attributes from backup.")
            raise click.ClickException(f"Validation error: {exc}") from exc
    else:
        click.echo("ome-zarr-models not installed; skipping strict validation.")

    click.echo("Metadata successfully written.")
