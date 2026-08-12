# Contract: Browse popup directory/file selection

Governs `tui/screens/browse_screen.py`'s `BrowsePickerScreen` — the shared
modal folder-tree used by every `PathField`'s Browse button, regardless of
which command's field opened it.

| Element | Rule |
|---|---|
| `only="dir"` fields | Clicking a directory's name (or `Enter` on a highlighted directory) dismisses the popup and fills the field with that directory's path. Clicking/selecting a file is a no-op — the popup stays open. **Unchanged by this feature.** |
| `only="file"` fields | Clicking a file's name (or `Enter`) dismisses the popup and fills the field. Clicking/selecting a directory is a no-op — the popup stays open (directories are still browsable: the click still expands/collapses via Textual's own default `NodeSelected` handling, it just never dismisses). **Unchanged by this feature.** |
| `only="any"` fields | Clicking either a file's name or a directory's name (or `Enter` on either) dismisses the popup and fills the field with the selected path. **This feature**: directory selection was previously a no-op here; it now behaves identically to file selection. |
| Expand/collapse icon | Clicking the tree's own expand/collapse toggle icon (not the name/label) only expands or collapses a directory, in every mode above — never selects, never dismisses. **Unaffected by this feature**, in every mode. |
| Overwrite/existing-content handling | Selecting an existing, non-empty directory dismisses and fills the field immediately, with no warning or confirmation — identical to selecting an existing file. The invoked command owns any overwrite semantics; the picker does not. |
| Cancel (`Escape`) | Dismisses with `None`; the originating field is left unchanged. **Unaffected by this feature.** |
| Root-path text input | Submitting a typed path re-roots the tree there if it's a valid directory; otherwise shows an error and the root is unchanged. **Unaffected by this feature.** |

## Affected fields today

- `from_images`'s `OUTPUT_ZARR` argument (`click.Path()`, both `file_okay`
  and `dir_okay` default `True` → `only="any"`) — the feature's driving
  example.
- `extract`'s `--output` option (`click.Path()`, same defaults → `only="any"`)
  — fixed by the same shared-component change, per clarification.

Any future field declared with a `click.Path()` that allows both files and
directories inherits this fix automatically — no per-field opt-in exists or
is needed.

## Who verifies this contract

- `tests/integration/test_tui_browse_picker.py` — existing tests already
  cover the `only="dir"` dismiss/no-dismiss rows and the expand/collapse-icon
  row (via `SafeDirectoryTree.filter_paths()`'s own `only="dir"`/`"any"`
  tests); new tests added by this feature cover the `only="any"`
  directory-name-click row specifically (`from_images`'s `OUTPUT_ZARR`) and a
  same-shape regression for `extract`'s `--output`.
