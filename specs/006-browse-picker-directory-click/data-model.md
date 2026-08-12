# Phase 1 Data Model: Browse picker directory-name click selects and closes

No persistent data entities are involved — this feature changes which of two
already-existing Textual messages a modal screen reacts to.

## Directory Selection (Browse popup)

**Represents**: The outcome of clicking a directory's name/label (or pressing
`Enter` on a highlighted directory) in `BrowsePickerScreen`'s folder tree —
whether that selection is valid for the field that opened the popup, and if
so, what happens.

**Representation**: `tui/screens/browse_screen.py`'s
`BrowsePickerScreen.only: Literal["dir", "file", "any"]` (unchanged, set at
construction from the originating field's `_path_only()` — `fields.py`) and
its `on_directory_tree_directory_selected()` handler:

```python
def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
    if self.only == "file":
        return
    self.dismiss(event.path)
```

| `only` | Directory-name click | File-name click (unchanged) |
|---|---|---|
| `"dir"` | Dismiss, fill field (unchanged) | No-op (unchanged) |
| `"file"` | No-op (unchanged) | Dismiss, fill field (unchanged) |
| `"any"` | **Dismiss, fill field (this feature)** | Dismiss, fill field (unchanged) |

**Relationships**: `event.path` (the selected directory's `Path`) is passed
straight to `self.dismiss(...)`, exactly as the file-selected handler already
does — `BrowsePickerScreen` is a `ModalScreen[Path | None]`, so this is the
same return-value channel `PathField`'s Browse button already awaits
(`fields.py`) to fill the originating `Input`. No new relationship is
introduced.

**Lifecycle**: Unchanged from the existing `only="dir"` path — a user clicks
a directory's name → Textual's `Tree._on_click()` posts `Tree.NodeSelected`
→ `DirectoryTree._on_tree_node_selected()` posts `DirectorySelected` →
`BrowsePickerScreen.on_directory_tree_directory_selected()` now dismisses for
`"any"` too → the awaiting `PathField` receives the `Path` and fills its
`Input` (`fields.py`, unchanged).
