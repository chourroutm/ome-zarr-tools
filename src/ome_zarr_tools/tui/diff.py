"""Side-by-side diff rendering for fix_metadata/migrate's Confirm and Result
screens: a "Current" panel beside a "Proposed" panel, each pretty-printed JSON
with changed/added/removed lines highlighted.

Uses the stdlib ``difflib`` over pretty-printed JSON (no new dependency,
research.md), restructured from a single unified +/- log into two side-by-side
panels per explicit user direction.
"""

from __future__ import annotations

import difflib
import json

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static


def _json_lines(value: dict | None) -> list[str]:
    if not value:
        return []
    return json.dumps(value, indent=2, sort_keys=True).splitlines()


def build_side_by_side_diff(before: dict | None, after: dict) -> Horizontal:
    """Two bordered, titled panels ("Current" / "Proposed") side by side, with
    replaced/removed lines highlighted red on the left and replaced/added lines
    highlighted green on the right."""
    before_lines = _json_lines(before)
    after_lines = _json_lines(after)

    left = Text()
    right = Text()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        before_block = before_lines[i1:i2]
        after_block = after_lines[j1:j2]
        # Pad the shorter side with blank lines so both panels advance by the
        # same number of rows per opcode block -- keeps unchanged lines after
        # a replace/insert/delete on the same row in both panels, instead of
        # drifting out of alignment once the two sides' line counts differ.
        block_len = max(len(before_block), len(after_block))
        for k in range(block_len):
            if k < len(before_block):
                left.append(before_block[k] + "\n", style="red" if tag != "equal" else None)
            else:
                left.append("\n")
            if k < len(after_block):
                right.append(after_block[k] + "\n", style="green" if tag != "equal" else None)
            else:
                right.append("\n")

    # Line-padding (above) keeps `left`/`right` non-empty even when `before`/
    # `after` themselves had no content, so check the originals here, not
    # whether the built `Text` is empty.
    left_panel = Static(left if before else Text("<none>", style="dim"), id="diff-current")
    left_panel.border_title = "Current"
    right_panel = Static(right if after else Text("<none>", style="dim"), id="diff-proposed")
    right_panel.border_title = "Proposed"

    for panel in (left_panel, right_panel):
        panel.styles.width = "1fr"
        panel.styles.height = "auto"
        panel.styles.border = ("solid", "grey")
        panel.styles.padding = (0, 1)

    diff = Horizontal(left_panel, right_panel, id="side-by-side-diff")
    diff.styles.height = "auto"  # Horizontal defaults to 1fr + hidden overflow -- would clip
    diff.styles.margin = (0, 1)  # Current's left margin matches Proposed's right margin
    return diff
