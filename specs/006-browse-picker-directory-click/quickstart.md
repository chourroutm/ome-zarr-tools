# Quickstart: Browse picker directory-name click selects and closes

## Prerequisites

- `uv sync` (or equivalent) so `ome-zarr-tools` and its test dependencies are installed.
- A scratch directory to browse into (any empty folder works).

## Automated validation

```sh
pytest tests/integration/test_tui_browse_picker.py -q
ruff check src tests && ruff format --check src tests && mypy src
```

Expected: all pass, including the new `only="any"` directory-name-click
regression tests. See
[contracts/browse-picker-contract.md](./contracts/browse-picker-contract.md)
for exactly what each row of behavior asserts.

## Manual walkthrough (real terminal)

1. Launch `ome-zarr-tools interactive --tui`.
2. Open `from_images`, tab to `OUTPUT_ZARR`, press its Browse button.
3. In the popup, click directly on a folder's **name** (not the small
   expand/collapse icon to its left). Confirm the popup closes immediately
   and `OUTPUT_ZARR` is filled with that folder's path.
4. Repeat, but this time click the expand/collapse icon instead — confirm
   the folder only expands/collapses and the popup stays open.
5. Open `extract`, tab to `--output`, press its Browse button, and repeat
   step 3 — confirm the same directory-name-click behavior.
6. Open `fix_metadata` (or `migrate`/`extract`/`inspect`'s `ZARR_PATH`),
   press its Browse button, and click a folder's name — confirm this
   already-working behavior is unchanged.
