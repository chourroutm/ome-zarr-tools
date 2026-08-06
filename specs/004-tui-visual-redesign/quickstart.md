# Quickstart: TUI Visual Redesign

Validation scenarios proving this feature works end-to-end. Prerequisites:
repo installed in editable mode (`pip install -e .[dev]`).

## Automated checks

```sh
ruff check src tests
ruff format --check src tests
mypy src/ome_zarr_tools
pytest
```

All four MUST pass, per this project's constitution Quality Gates. New
tests (see `contracts/visual-design-contract.md`'s "Who verifies") prove
each user story; existing `tests/integration/test_interactive_tui.py`,
`test_tui_shortcuts.py`, and `test_tui_structure.py` must keep passing
unchanged in behavior — this feature changes field layout/labels/widgets,
not the `003` shortcut/structure contracts.

## Manual walkthrough (User Story 1 — logo, menu entries, clock)

1. `ome-zarr-tools interactive --tui`
2. Confirm the ASCII logo renders above the command list at a normal
   terminal size; shrink the terminal and confirm it disappears cleanly
   (no clipped/corrupted output) rather than crowding the list.
3. Confirm each command entry spans 3 lines (name, help text, blank), with
   arrow-key/click selection and Enter-to-open still working.
4. Confirm the header shows a live clock, and that it's still there after
   opening any command screen.

## Manual walkthrough (User Story 2/3 — frames, labels)

1. Open `from_images` (mixed required/optional fields). Confirm a
   "Required" frame appears above an "Optional" frame, each bordered and
   titled.
2. Confirm every field label reads as human-readable text (e.g. "Voxel
   Size Unit"), not a raw flag.
3. Open `inspect` (all-required, single field). Confirm only the Required
   frame appears — no empty Optional frame.
4. Fill in a form, press Copy, and confirm the clipboard content still uses
   the original CLI flags, unaffected by frames/labels.

## Manual walkthrough (User Story 4 — Browse picker)

1. Open a form with a path field (e.g. `inspect`'s `zarr_path`). Confirm a
   "Browse" button (3 rows tall) sits to the right of the input.
2. Press it; confirm a directory-tree view opens rooted near the field's
   current value (or cwd if empty).
3. Select an entry; confirm the field is filled and every other field is
   untouched.
4. Reopen Browse and cancel (Escape); confirm the field is unchanged.

## Manual walkthrough (User Story 5 — remote path add-on)

1. In a path field, type `gs://my-bucket/data.zarr`. Confirm a blue
   `gs://` add-on appears with `my-bucket/data.zarr` as the only editable
   text, and no local autocomplete suggestions appear.
2. Repeat with `s3://` (orange), `az://` or `abfs://` (cyan), and `http://`
   or `https://` (gray).
3. Backspace the remainder down to nothing; confirm the add-on disappears
   and the scheme reappears as plain editable text, deletable like any
   other character.
4. Copy the field's value at each stage and confirm it always matches what
   was actually typed (scheme + remainder), regardless of add-on state.
