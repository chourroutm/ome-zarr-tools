# Phase 0 Research: Browse picker directory-name click selects and closes

## Decision: Fix `BrowsePickerScreen.on_directory_tree_directory_selected()`, mirror the existing file-selected guard

**Decision**: Change

```python
def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
    if self.only == "dir":
        self.dismiss(event.path)
```

to

```python
def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
    if self.only == "file":
        return
    self.dismiss(event.path)
```

so it dismisses whenever the field doesn't exclusively want a file — i.e. for
both `only="dir"` (unchanged behavior) and `only="any"` (the fix). This
exactly mirrors the sibling handler already in the same class:

```python
def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
    if self.only == "dir":
        return
    self.dismiss(event.path)
```

**Rationale**: `only` has three values (`"dir"`, `"file"`, `"any"`), and the
two selected-handlers are meant to be exact opposites of each other — file
selection is valid whenever `only != "dir"`, directory selection is valid
whenever `only != "file"`. The existing code only implemented that symmetry
for the file-selected handler; the directory-selected handler used `== "dir"`
(only the narrow case) instead of `!= "file"` (the correct broad case),
which is exactly why `only="any"` fell through and did nothing. This is a
one-line-equivalent fix restoring the symmetry that was clearly already
intended by the sibling method's own guard.

**Alternatives considered**:
- *Special-case `from_images`'s `output_zarr` field alone* (e.g. a new
  parameter threaded through `PathField`/`BrowsePickerScreen`) — rejected per
  clarification: the gap is in the shared component and affects any
  `only="any"` field (`extract`'s `--output` today too); a per-field special
  case would leave `extract` with the same broken interaction for no reason
  a user could tell apart from `from_images`.
- *Change `SafeDirectoryTree`/override `Tree._on_click` directly* — rejected.
  The existing `BrowsePickerScreen` already reacts to Textual's own
  `DirectoryTree.FileSelected`/`DirectorySelected` messages (posted for
  every valid selection path — mouse click on the label, or `Enter` on the
  highlighted node); there is no need to intercept lower-level click/key
  events when the message-handler layer already receives exactly the signal
  needed, just with an incomplete guard.

## Decision: No confirmation/warning added for selecting a non-empty existing directory

**Decision**: `on_directory_tree_directory_selected()` dismisses
unconditionally (once past the `only == "file"` guard) — no check of the
directory's contents, no confirmation dialog.

**Rationale**: Per clarification, this must behave identically to selecting
an existing file today, which has never warned about overwriting. Adding a
warning only for directories would be a new, asymmetric interaction not
present anywhere else in this picker, and the commands that actually write
to `OUTPUT_ZARR`/`--output` already own their own overwrite semantics
(that decision belongs to the command being invoked, not the path picker).

**Alternatives considered**: A `self.notify(...)` warning shown after
dismissal, listing the directory's existing contents — rejected as
out-of-scope per the clarification and not something any other Browse
popup interaction does today.
