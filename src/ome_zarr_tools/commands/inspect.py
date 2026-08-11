from __future__ import annotations

import json
import math

import click
import zarr

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.zarr_path import ZarrPathParamType
from ome_zarr_tools.io.ome_metadata import read_multiscales, validate


def _stored_bytes(array: zarr.Array) -> int | None:
    """On-disk size, or ``None`` if the store can't report it (e.g. a remote store that
    allows anonymous object reads but denies the bucket-listing needed to sum chunk sizes).
    """
    try:
        return int(array.nbytes_stored())
    except Exception:
        return None


def _level_report(group: zarr.Group, dataset_path: str) -> dict:
    array = group[dataset_path]
    if not isinstance(array, zarr.Array):
        raise CliError(f"{dataset_path!r} is not an array in this dataset.")
    logical_bytes = int(math.prod(array.shape)) * array.dtype.itemsize
    return {
        "path": dataset_path,
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "chunk_shape": list(array.chunks),
        "shard_shape": list(array.shards) if array.shards is not None else None,
        "stored_bytes": _stored_bytes(array),
        "logical_bytes": int(logical_bytes),
    }


def build_report(zarr_path: str) -> dict:
    try:
        group = zarr.open_group(zarr_path, mode="r")
    except Exception as exc:
        raise CliError(
            f"No Zarr group found at {zarr_path}. "
            "The path may not be a valid Zarr store, or the dataset may be incomplete "
            f"(e.g. still downloading). Details: {exc}"
        ) from exc
    multiscales = read_multiscales(group)
    if not multiscales:
        raise CliError(f"No multiscales metadata found in {zarr_path}.")

    levels = [
        _level_report(group, dataset["path"]) for dataset in multiscales[0].get("datasets", [])
    ]
    is_valid, _error = validate(group)
    stored_bytes = [level["stored_bytes"] for level in levels]
    total_stored_bytes = sum(stored_bytes) if all(b is not None for b in stored_bytes) else None

    return {
        "dataset": str(zarr_path),
        "levels": levels,
        "total_stored_bytes": total_stored_bytes,
        "total_logical_bytes": sum(level["logical_bytes"] for level in levels),
        "metadata_valid": is_valid,
    }


def format_text(report: dict) -> str:
    lines = [f"Dataset: {report['dataset']}", f"Metadata valid: {report['metadata_valid']}", ""]
    for level in report["levels"]:
        lines.append(f"Level {level['path']}:")
        lines.append(f"  shape:        {tuple(level['shape'])}")
        lines.append(f"  dtype:        {level['dtype']}")
        lines.append(f"  chunk shape:  {tuple(level['chunk_shape'])}")
        shard_shape = tuple(level["shard_shape"]) if level["shard_shape"] else "none"
        lines.append(f"  shard shape:  {shard_shape}")
        lines.append(f"  stored size:  {_format_bytes(level['stored_bytes'])}")
        lines.append(f"  logical size: {level['logical_bytes']} bytes")
        lines.append("")
    lines.append(f"Total stored size:  {_format_bytes(report['total_stored_bytes'])}")
    lines.append(f"Total logical size: {report['total_logical_bytes']} bytes")
    return "\n".join(lines)


def _format_bytes(value: int | None) -> str:
    return f"{value} bytes" if value is not None else "unknown (store denied listing)"


@click.command(name="inspect")
@click.argument("zarr_path", type=ZarrPathParamType(exists=True, file_okay=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def inspect(zarr_path: str, output_format: str) -> None:
    """Report shape, chunk/shard layout, and on-disk vs. logical size for ZARR_PATH. Read-only."""
    report = build_report(zarr_path)
    if output_format == "json":
        click.echo(json.dumps(report, indent=2))
    else:
        click.echo(format_text(report))
