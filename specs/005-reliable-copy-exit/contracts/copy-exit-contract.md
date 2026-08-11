# Contract: Reliable Copy & Exit

## Exit-time printed fallback (User Story 1)

| Element | Rule |
|---|---|
| Trigger | Any per-command screen's "Copy & exit" shortcut (`F7`, `shared_bindings()`'s `copy_and_exit` action) — and only that action; every other exit path (`Cancel`, menu `Back`, a Result/Confirm screen's return shortcut, plain "Copy" without exiting) is unaffected and continues to exit with `result=None` (FR-006). |
| App type | `InteractiveTUIApp(App[str | None])` (was `App[None]`) — the only type-signature change; no other `App`/`Screen[...]` in this codebase changes. |
| Screen behavior | `action_copy_and_exit()` calls the existing `self.action_copy()` unchanged (still attempts `App.copy_to_clipboard()` — FR-002), then `self.app.exit(result=self._invocation_text())` in place of `result=None`. Applies identically to all 5 existing implementations: `CommandFormScreen` (`tui/app.py`), `InspectScreen`, `_BaseMetadataScreen` (fix_metadata/migrate Form), `_BaseConfirmScreen` (fix_metadata/migrate Confirm, spec 004 US8), `ConfigScreen` (FR-004). |
| CLI-side print | `commands/interactive.py`'s `--tui` path: `invocation = app.run(); if invocation: click.echo(f"Copied invocation: {invocation}")`. Printed only after `app.run()` returns, i.e. only once Textual has fully restored the terminal (FR-001/FR-003). |
| Output format | `click.echo()`, never bare `print()` — composes with `CliRunner` output capture like every other command. Exact text: `Copied invocation: {invocation}`, where `{invocation}` is byte-for-byte the same string passed to `copy_to_clipboard()` (FR-005). |
| Unconditional | The printed line always appears on "Copy & exit," regardless of whether the clipboard attempt actually reached a real clipboard — the app has no way to detect that, so it never tries to (FR-007). |

## Who implements this contract

- `commands/interactive.py` — captures `app.run()`'s return value, prints via `click.echo()`
- `tui/app.py` — `InteractiveTUIApp(App[str | None])`, `CommandFormScreen.action_copy_and_exit()`
- `tui/screens/inspect_screen.py` — `InspectScreen.action_copy_and_exit()`
- `tui/screens/metadata_screen.py` — `_BaseMetadataScreen.action_copy_and_exit()`, `_BaseConfirmScreen.action_copy_and_exit()`
- `tui/screens/config_screen.py` — `ConfigScreen.action_copy_and_exit()`

## Who verifies this contract

- Per-screen tests (`tests/integration/test_tui_copy_exit.py`, new): for each
  of the 5 screens, fill in fields, press `F7` (Copy & exit) inside
  `App.run_test()`, and assert the pilot's captured exit result equals the
  expected invocation string.
- A `CliRunner`-based test (`tests/integration/test_interactive.py` or new):
  drives `ome-zarr-tools interactive --tui` end-to-end (headless) through a
  Copy & exit action and asserts `"Copied invocation: "` plus the expected
  tokens appear in `result.output`.
- A regression test confirming plain "Copy" (no exit) and every other exit
  path still exit with a falsy result and print nothing.
