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
unchanged in behavior for everything except Run's own behavior and two
additive shortcuts (User Story 7's deliberate changes) — the rest of the
shortcut set and the `003` header/status-log/footer skeleton are otherwise
untouched.

## Manual walkthrough (User Story 1 — logo, menu entries)

1. `ome-zarr-tools interactive --tui`
2. Confirm the ASCII logo renders above the command list at a normal
   terminal size; shrink the terminal and confirm it disappears cleanly
   (no clipped/corrupted output) rather than crowding the list.
3. Confirm each command entry spans 3 lines (name, help text, blank), with
   arrow-key/click selection and Enter-to-open still working.

## Manual walkthrough (User Story 2/3 — frames, labels)

1. Open `from_images` (mixed required/optional fields). Confirm a
   "Required" frame (solid red border) appears above an "Optional" frame
   (solid blue border), each titled.
2. Confirm the Required frame's subtitle shows the correct count of empty
   required fields (e.g. "3 remaining"); fill one in and confirm the count
   decreases by one; fill in all of them and confirm it reads
   "0 remaining".
3. Confirm every field label reads as human-readable text (e.g. "Voxel
   Size Unit"), not a raw flag.
4. Open `inspect` (all-required, single field). Confirm only the Required
   frame appears — no empty Optional frame.
5. Fill in a form, press Copy, and confirm the clipboard content still uses
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

## Manual walkthrough (User Story 6 — command identity frame)

1. Open any command's prep screen (generic or specialized). Confirm a
   borderless block appears above the field content, showing the
   command's name in bold with its CLI description underneath, and a bit
   of padding around both.
2. Confirm the description text matches the same text shown for that
   command in the menu's second line, and that even a long description
   never grows past 3 lines.
3. Confirm the identity block is visually distinguishable from the
   required/optional field-group frames (User Story 2) on the same
   screen — no border/title, unlike the field-group frames' solid
   borders.

## Manual walkthrough (User Story 7 — command result screen, progress, Restore Defaults)

1. Open `from_images`, fill in all required fields (pick a slow-enough
   input to actually see the pending state — a large stack directory
   works well), press Run.
2. Confirm the app navigates to a Result screen *immediately*, before the
   command finishes — showing the same command-identity frame as the prep
   screen, and a progress bar (once quantifiable) or an animated
   sparkline (before then) in place of any outcome content.
3. Once the command finishes, confirm that same screen swaps the progress
   indicator for a success indicator, the execution log, and the
   command's specific output.
4. Press "Back to form" (footer shortcut, labeled differently from every
   other screen's "Back to menu"); confirm the app returns to the
   `from_images` prep screen with every field exactly as it was before
   Run.
5. Repeat with a Run that fails (e.g. an invalid path); confirm the
   Result screen's progress indicator is replaced by a failure indicator
   and the error message instead.
6. Repeat with a required field left empty and press Run; confirm the app
   does *not* navigate anywhere — the existing inline "field is required"
   notification still applies.
7. Run `inspect`; confirm its Result screen shows the summary/JSON report
   panels once finished. Run `fix_metadata` or `migrate`; confirm its
   Result screen shows the diff that was applied. Run `config`; confirm
   its Result screen shows the written config JSON.
8. Start a run, then press "Back to form" while it's still pending;
   confirm you're back on the prep screen with fields disabled; press Run
   again and confirm it re-navigates to the *same* pending Result screen
   rather than starting a second execution.
9. On any prep screen, change a few field values, then press Restore
   Defaults (`F4`); confirm the screen reloads (a fresh instance) and
   every field shows the value it had when the screen first opened
   (including any non-empty default, e.g. `migrate`'s `--target_version`)
   — not necessarily blank. On `fix_metadata`/`migrate`/`config`, also
   confirm their diff/current-config view resets along with the fields.
10. Start a run, and while fields are disabled, press Restore Defaults; confirm it
    has no effect until the run finishes.
