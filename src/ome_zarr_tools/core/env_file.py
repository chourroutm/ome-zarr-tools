"""Plain ``KEY=VALUE`` env-file I/O, shared by ``commands/config.py`` and the
top-level ``--env-file`` option (``cli.py``).

Values are always kept as raw strings -- type conversion into an option's
real type is deferred entirely to click's own ``ParamType.convert()`` when a
value flows through ``Context.default_map`` (research.md §3).
"""

from __future__ import annotations

import re
from pathlib import Path

from ome_zarr_tools.core.errors import CliError

_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_valid_env_key(key: str) -> bool:
    return bool(_ENV_KEY_PATTERN.match(key))


def parse_env_text(text: str, *, source: str = "<text>") -> tuple[dict[str, str], list[str]]:
    """Parse ``KEY=VALUE`` lines out of ``text``. Returns ``(values, duplicate_warnings)``.

    Blank lines and ``#``-prefixed comment lines are skipped. A line with no
    ``=`` raises ``CliError`` naming ``source`` and its 1-indexed line number.
    A key repeated across multiple lines keeps the last occurrence's value;
    one warning is generated per duplicated key (FR-015). Shared by
    ``read_env_file`` and the TUI's ``ConfigScreen`` editor, so both parse
    exactly the same way.
    """
    values: dict[str, str] = {}
    warnings: list[str] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise CliError(f"{source}:{line_number}: expected KEY=VALUE, got: {raw_line!r}")
        key, value = line.split("=", 1)
        key = key.strip()
        if key in values:
            warnings.append(f"Duplicate key {key!r} in {source}; using the last occurrence.")
        values[key] = value.strip()
    return values, warnings


def read_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """Parse ``path``. Returns ``(values, duplicate_warnings)`` -- see ``parse_env_text``."""
    if not path.exists():
        raise CliError(f"{path} does not exist.")
    return parse_env_text(path.read_text(encoding="utf-8"), source=str(path))


def write_env_file(path: Path, values: dict[str, str]) -> None:
    """Write one ``KEY=VALUE`` line per entry (insertion order), overwriting
    anything already at ``path``. Comments/blank lines from a prior version
    are not preserved (an edit-and-rewrite model, not an in-place patch)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
