"""A Zarr path may be a local filesystem path or a remote store URL (``gs://``, ``s3://``, ...).

``zarr`` (>=3) opens remote URLs natively via ``fsspec`` once the matching
optional filesystem package (``gcsfs``, ``s3fs``, ...) is installed --
``pip install ome-zarr-tools[remote]``. The only local-specific piece is
argument validation: ``click.Path(exists=True)`` checks the local filesystem
and rejects any URL outright, before the command body ever runs.
"""

from __future__ import annotations

import os

import click

_REMOTE_SCHEMES = ("gs://", "gcs://", "s3://", "http://", "https://", "az://", "abfs://")


def is_remote_path(value: str) -> bool:
    return value.startswith(_REMOTE_SCHEMES)


class ZarrPathParamType(click.Path):
    """Like ``click.Path``, but skips the local-existence check for remote URLs.

    A remote store's existence can only be confirmed by actually opening it
    (network round-trip, possibly requiring credentials) -- that check belongs
    to the command itself (and its own clean ``CliError`` on failure), not to
    argument parsing.
    """

    def convert(
        self,
        value: str | os.PathLike[str],
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> str | bytes | os.PathLike[str]:
        if isinstance(value, str) and is_remote_path(value):
            return value
        return super().convert(value, param, ctx)
