"""Command menu logo (spec 004 US1): three OME-colored squares, side by side.

Colors sourced from openmicroscopy.org's own stylesheet (usage-frequency
scan of its CSS), with the green adjusted from an initially-scraped
``#128669`` -- that value and the blue collapse to the same standard-16
ANSI color on terminals without truecolor support, making them
indistinguishable. ``#16a34a`` downgrades to actual ANSI green instead.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

OME_RED = "#df283f"
OME_GREEN = "#16a34a"
OME_BLUE = "#1d8dcd"

LOGO_BOXES = [(4, OME_RED), (3, OME_GREEN), (2, OME_BLUE)]
LOGO_GAP = 2
LOGO_FILL = "█"

# Terminal character cells are roughly twice as tall as they are wide, so a
# box that's N columns by N rows of full-block characters renders as a
# vertical rectangle, not a square. Doubling the column count per row of
# height compensates for that, so "side N" reads as an actually-square box.
LOGO_WIDTH_ASPECT = 2

LOGO_MIN_WIDTH = 40
LOGO_MIN_HEIGHT = 15


def _box_rows() -> list[list[tuple[str, str | None]]]:
    """3 filled, bottom-aligned squares (sides 4/3/2) side by side, one OME
    color each, separated by blank gaps."""
    height = max(side for side, _ in LOGO_BOXES)
    rows: list[list[tuple[str, str | None]]] = []
    for r in range(height):
        row: list[tuple[str, str | None]] = []
        for i, (side, color) in enumerate(LOGO_BOXES):
            if i:
                row.append((" " * LOGO_GAP, None))
            top_of_box = height - side
            width = side * LOGO_WIDTH_ASPECT
            row.append((LOGO_FILL * width if r >= top_of_box else " " * width, color))
        rows.append(row)
    return rows


def render_logo() -> Text:
    art_text = Text()
    for i, row in enumerate(_box_rows()):
        if i:
            art_text.append("\n")
        for segment, color in row:
            art_text.append(segment, style=f"bold {color}" if color else None)
    return art_text


class Logo(Static):
    """The command menu's logo. Hidden (not clipped) below a minimum terminal size.

    Visibility is driven by the owning screen's ``on_resize`` (see
    ``CommandMenuScreen``) calling ``set_visible_for_size()`` -- a plain
    ``Static`` widget's own resize events reflect its *own* allocated size
    (fixed by ``height: auto``), never the terminal's actual dimensions, so
    the size check can't live inside ``Logo`` itself.
    """

    DEFAULT_CSS = """
    Logo {
        content-align: center middle;
        height: auto;
        padding: 1 0;
    }
    """

    def __init__(self) -> None:
        super().__init__(render_logo())

    def set_visible_for_size(self, width: int, height: int) -> None:
        self.display = width >= LOGO_MIN_WIDTH and height >= LOGO_MIN_HEIGHT
