# Phase 1 Data Model: Consistent TUI Menus & Forms

No persisted or transmitted data entities are introduced by this feature —
it's a UI-structure change to an existing, already-implemented TUI. The
"entities" from the spec map onto existing (or one new, small) code
constructs as follows.

## Command Screen

**What it represents**: Any full-screen `textual.screen.Screen` a user can be
on: the command menu (`CommandMenuScreen`), the generic form screen shared by
`from_images`/`extract`/`apply_mask` (`CommandFormScreen`), or one of the four
specialized screens (`InspectScreen`, `FixMetadataScreen`, `MigrateScreen`,
`ConfigScreen`).

**Fields/attributes** (unchanged by this feature, restated for reference):
- `BINDINGS: list[Binding]` — keyboard shortcuts, now built from
  `shared_bindings()` (see below) plus any screen-specific extras.
- A header (`Header()`), a scrollable command-specific content area, and
  (except for `CommandMenuScreen`) a status/log region (`StatusPanel`)
  docked directly above the footer.

**Validation rules**: A per-command screen's `BINDINGS` prefix MUST equal
`shared_bindings()`'s `(key, action)` pairs, in order (label may differ only
for the primary/`run` slot). Enforced by a new static test, not runtime
validation — there is no user-facing "invalid state" here, only a
developer-facing regression guard.

## Shared Shortcut Set

**What it represents**: The fixed, ordered list of `(key, action, label)`
triples every per-command screen exposes: `f5`/`run`/`"Run"` (or a
screen-appropriate label), `f6`/`copy`/`"Copy"`, `f7`/`copy_and_exit`/`"Copy
& exit"`, `f8`/`toggle_log`/`"Log"`, `escape`/`back`/`"Back to menu"`,
`ctrl+c`/`cancel`/`"Cancel"`.

**Representation**: `shared_bindings(primary_label: str = "Run") ->
list[Binding]` in new module `src/ome_zarr_tools/tui/shortcuts.py` — a plain
function returning `Binding` instances, not a class or registry. No state,
no persistence.

**Relationships**: Consumed by every per-command screen's `BINDINGS` class
attribute (`BINDINGS = [*shared_bindings(), Binding("f9", ...)]` for
`InspectScreen`; `BINDINGS = [*shared_bindings(primary_label="Save")]` for
`ConfigScreen`; etc.).

## Command-Preview Panel

**What it represents**: The now-removed live "$ ome-zarr-tools \<command\>
..." `Label` previously rendered in `CommandFormScreen`. After this feature,
it no longer exists as a rendered widget anywhere in the TUI; it survives
only as the pure `_invocation_text()` method each screen already has,
computed on demand when Copy/Copy & exit is pressed.

**State transition**: Rendered widget → deleted. No replacement widget is
introduced (per spec Assumptions: no new preview mechanism was requested).
