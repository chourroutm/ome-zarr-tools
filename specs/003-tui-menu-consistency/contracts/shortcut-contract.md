# Contract: Shared TUI Shortcut Set

This is the interface every per-command TUI screen commits to. It is the
thing `shared_bindings()` (see `research.md`/`data-model.md`) implements and
the thing the new regression test asserts against.

## Canonical shared shortcuts (in order)

| Key      | Action           | Default Label | Per-screen override allowed? |
|----------|------------------|----------------|-------------------------------|
| `f5`     | `run`            | `Run`          | Label only (e.g. `Save` for `config`) |
| `f6`     | `copy`           | `Copy`         | No |
| `f7`     | `copy_and_exit`  | `Copy & exit`  | No |
| `f8`     | `toggle_log`     | `Log`          | No |
| `escape` | `back`           | `Back to menu` | No |
| `ctrl+c` | `cancel`         | `Cancel`       | No |

## Rules

1. Every per-command screen's `BINDINGS` MUST start with exactly these six
   entries, in this order, with these keys and action names.
2. Only the `f5`/`run` entry's **label** may be overridden per screen; its
   key and action name MUST NOT change.
3. Any screen-specific additional binding (e.g. `inspect`'s `f9` /
   `switch_panel` / `"Switch panel"`) MUST be appended after all six shared
   entries, never before or interleaved.
4. The command menu screen (`CommandMenuScreen`) is exempt from entries 1–3
   (it has no command to run/copy) but MUST still use `escape`/`ctrl+c` →
   `cancel` and the same `Header()`/`Footer()` chrome as every other screen
   (FR-008).
5. `action_copy`/`action_copy_and_exit` on every per-command screen MUST
   place the exact current CLI invocation on the clipboard, computed via
   that screen's own `_invocation_text()`, regardless of whether any
   preview of that text is ever rendered on screen.

## Who implements this contract

- `src/ome_zarr_tools/tui/shortcuts.py` — `shared_bindings()`, the single
  source of truth for rows 1–4 above.
- `src/ome_zarr_tools/tui/app.py` — `CommandMenuScreen`, `CommandFormScreen`
- `src/ome_zarr_tools/tui/screens/inspect_screen.py` — `InspectScreen`
- `src/ome_zarr_tools/tui/screens/metadata_screen.py` — `FixMetadataScreen`,
  `MigrateScreen`
- `src/ome_zarr_tools/tui/screens/config_screen.py` — `ConfigScreen`

## Who verifies this contract

A new static test (proposed location: `tests/integration/test_tui_shortcuts.py`)
that imports every screen class above, reads its `BINDINGS`, and asserts rows
1–3 hold for all of them, plus a clipboard-content test per generic-form
command (`from_images`/`extract`/`apply_mask`) asserting rule 5 continues to
hold once the visible preview panel is removed.
