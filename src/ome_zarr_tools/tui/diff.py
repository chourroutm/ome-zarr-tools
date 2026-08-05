"""Diff rendering for fix_metadata/migrate's Diff View (FR-018).

Uses the stdlib ``difflib`` over pretty-printed JSON, colored via Rich ``Text``,
rendered into a ``RichLog`` -- no new dependency (research.md).
"""

from __future__ import annotations

import difflib
import json

from rich.text import Text
from textual.widgets import RichLog


def diff_lines(before: dict | None, after: dict) -> list[Text]:
    """Return styled +/- lines comparing ``before`` (or empty/None) to ``after``."""
    before_text = json.dumps(before, indent=2, sort_keys=True).splitlines() if before else []
    after_text = json.dumps(after, indent=2, sort_keys=True).splitlines()
    diff = difflib.unified_diff(
        before_text, after_text, fromfile="before", tofile="after", lineterm=""
    )
    lines: list[Text] = []
    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            lines.append(Text(line, style="bold"))
        elif line.startswith("+"):
            lines.append(Text(line, style="green"))
        elif line.startswith("-"):
            lines.append(Text(line, style="red"))
        elif line.startswith("@@"):
            lines.append(Text(line, style="cyan"))
        else:
            lines.append(Text(line))
    return lines


def render_diff(log: RichLog, before: dict | None, after: dict) -> None:
    """Clear ``log`` and write the diff between ``before`` and ``after`` into it."""
    log.clear()
    for line in diff_lines(before, after):
        log.write(line)
