# Quickstart: Consistent TUI Menus & Forms

Validation scenarios proving this feature works end-to-end. Prerequisites:
repo installed in editable mode (`pip install -e .[dev]`), a small local
OME-Zarr fixture for `inspect`/`fix_metadata`/`migrate` if you want to
exercise those screens manually (not required for the automated checks
below).

## Automated checks

```sh
ruff check src tests
ruff format --check src tests
mypy
pytest
```

All four MUST pass, per this project's constitution Quality Gates. The new
test added for this feature (`tests/integration/test_tui_shortcuts.py`, see
`contracts/shortcut-contract.md`) specifically proves User Story 1's shared
shortcut set is consistent across every command screen; the updated
`CommandFormScreen` tests in `tests/integration/test_interactive_tui.py`
prove User Story 2 (no visible preview, Copy/Copy & exit still correct).

## Manual walkthrough (User Story 1 — shortcut consistency)

1. `ome-zarr-tools interactive --tui`
2. Open each command in turn (`from_images`, `extract`, `apply_mask`,
   `fix_metadata`, `migrate`, `inspect`, `config`) and look at the footer.
3. Confirm: the same six shortcuts (Run/Save, Copy, Copy & exit, Log, Back to
   menu, Cancel) appear bound to F5–F8/Escape/Ctrl+C in the same order on
   every screen; `inspect`'s extra "Switch panel" (F9) appears after them,
   not before or in between.

## Manual walkthrough (User Story 2 — no command-preview panel)

1. From the TUI menu, open `from_images`.
2. Fill in a few fields.
3. Confirm no "$ ome-zarr-tools from_images ..." line appears anywhere on
   screen, at any point.
4. Press Copy (F6). Paste the clipboard contents somewhere and confirm it's
   the exact, correct CLI invocation for the values you entered.
5. Repeat steps 1–4 for `extract` and `apply_mask`.

## Manual walkthrough (User Story 3 — structural skeleton)

1. Open each of the seven command screens.
2. Confirm each has exactly one header at top, one footer at bottom, and one
   status/log region directly above the footer — with the command-specific
   content (form fields / diff view / JSON panels / config editor) filling
   the scrollable area between the header and that status/log region.
3. Open the command menu itself and confirm it shares the same
   header/footer chrome, without a status/log region (it doesn't run a
   command directly).
