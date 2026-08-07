"""Browse picker (spec 004 US4): a directory-tree modal for filling a path field.

``SafeDirectoryTree`` mirrors ``fields.py``'s ``SafePathAutoComplete`` --
tolerates permission-denied entries instead of crashing (FR-012) -- and
constrains which entries are shown per the field's declared type
(directory-only, file-only, or either; FR-011).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree


class SafeDirectoryTree(DirectoryTree):
    def __init__(
        self,
        path: str | Path,
        *,
        only: Literal["dir", "file", "any"] = "any",
        id: str | None = None,  # noqa: A002
    ) -> None:
        super().__init__(path, id=id)
        self.only = only

    def filter_paths(self, paths):  # noqa: ANN001
        result = []
        for entry in paths:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue  # permission-denied entry: skip, don't crash (FR-012)
            if self.only == "dir" and not is_dir:
                continue
            result.append(entry)
        return result


class BrowsePickerScreen(ModalScreen[Path | None]):
    """Pick a local path. Dismisses with the selected `Path`, or `None` on cancel."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    BrowsePickerScreen {
        align: center middle;
    }
    BrowsePickerScreen > SafeDirectoryTree {
        width: 80%;
        height: 80%;
        border: round $panel;
    }
    """

    def __init__(self, root: Path, only: Literal["dir", "file", "any"] = "any") -> None:
        super().__init__()
        self.root = root
        self.only = only

    def compose(self) -> ComposeResult:
        yield SafeDirectoryTree(self.root, only=self.only)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        if self.only == "dir":
            return
        self.dismiss(event.path)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if self.only == "dir":
            self.dismiss(event.path)

    def action_cancel(self) -> None:
        self.dismiss(None)
