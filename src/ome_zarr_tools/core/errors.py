"""Shared exit-code / error-message conventions (FR-004, FR-006).

Commands raise ``CliError`` (or a subclass) for any expected failure — bad
input, a missing optional dependency, an unrecognized dataset layout. Click
catches it, prints ``Error: {message}`` to stderr, and exits non-zero.
"""

from __future__ import annotations

import click


class CliError(click.ClickException):
    """An expected, user-facing failure."""


class MissingDependencyError(CliError):
    def __init__(self, package: str, feature: str) -> None:
        super().__init__(f"'{package}' is required for {feature} but is not installed.")
