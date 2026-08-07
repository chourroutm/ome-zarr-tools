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
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Footer, Input


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
        self.show_root = False  # the root path is already shown in #root-path-input

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
    """Pick a local path. Dismisses with the selected `Path`, or `None` on cancel.

    ``DirectoryTree`` only shows the root it's given and its descendants -- there's
    no built-in way to reach an ancestor directory. An editable path `Input`
    (pre-filled with the tree's current root -- the field's current value's parent
    directory, or cwd if the field was empty, per `PathField`'s existing rooting
    rule) sits above the tree; submitting it (Enter) re-roots the tree at the typed
    path if it's a valid directory, letting the user jump anywhere -- including
    above the initial root -- by typing rather than depending on a specific key
    (an earlier "Up"/Backspace-only design turned out not to work reliably across
    terminals/multiplexers).
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    BrowsePickerScreen {
        align: center middle;
    }
    BrowsePickerScreen > Vertical {
        width: 80%;
        height: 80%;
        border: round $panel;
    }
    BrowsePickerScreen > Vertical > Input {
        margin: 0 1;
    }
    BrowsePickerScreen > Vertical > SafeDirectoryTree {
        height: 1fr;
        margin: 0 1;
        padding: 0 2;
        border: tall $border-blurred;
    }
    """

    def __init__(self, root: Path, only: Literal["dir", "file", "any"] = "any") -> None:
        super().__init__()
        self.root = root
        self.only = only

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(str(self.root), id="root-path-input")
            yield SafeDirectoryTree(self.root, only=self.only)
        yield Footer()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        if self.only == "dir":
            return
        self.dismiss(event.path)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if self.only == "dir":
            self.dismiss(event.path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "root-path-input":
            return
        event.stop()
        candidate = Path(event.value).expanduser()
        if not candidate.is_dir():
            self.notify(f"Not a directory: {candidate}", severity="error")
            return
        self.root = candidate
        self.query_one(SafeDirectoryTree).path = candidate

    def action_cancel(self) -> None:
        self.dismiss(None)
