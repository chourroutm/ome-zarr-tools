# Phase 0 Research: Consistent TUI Menus & Forms

## Baseline audit (done before deciding anything)

Read every `BINDINGS` list in `src/ome_zarr_tools/tui/app.py` and
`src/ome_zarr_tools/tui/screens/*.py`, and every use of `_invocation_text()`/
the invocation-preview widget, to establish what's actually true today versus
what the spec assumed.

**Findings**:

- The five screens with a primary action (`CommandFormScreen`,
  `InspectScreen`, `FixMetadataScreen`, `MigrateScreen`, `ConfigScreen`)
  already declare `f5`/`f6`/`f7`/`f8`/`escape`/`ctrl+c` bound to
  `run`/`copy`/`copy_and_exit`/`toggle_log`/`back`/`cancel` respectively, in
  that exact order. `InspectScreen` already appends its screen-specific
  `f9`/`switch_panel` *after* the shared six, not interleaved.
  `ConfigScreen`'s `f5` binding already uses the label `"Save"` while keeping
  the same key and action name (`run`). In other words, FR-001/FR-002/FR-003
  are **already satisfied at the data level** — by five independently
  hand-written, identical-by-coincidence lists.
- The live "$ ome-zarr-tools ... " command-preview `Label` (`_invocation_label`
  / `_refresh_invocation`) exists **only** in `CommandFormScreen`
  (`app.py`), which is the screen `from_images`, `extract`, and
  `apply_mask` all share. None of the four specialized screens
  (`inspect`, `config`, `fix_metadata`, `migrate`) render it — they already
  compute `_invocation_text()` purely, on demand, for Copy/Copy & exit only.
  So FR-004's target pattern (compute the invocation for Copy without
  displaying it) is already the codebase's majority pattern; only
  `CommandFormScreen` is the outlier.
- `tests/integration/test_interactive_tui.py` already asserts against
  `app.screen._invocation_text()` (a method), never against the `Label`
  widget's rendered text — so removing the widget doesn't require rewriting
  those assertions, only removing the now-dead `on_mount`/`_refresh_invocation`
  wiring around it.

This changes the shape of the plan: the work is not "invent consistency from
scratch," it's (a) a small, mechanical removal in one screen, and (b) turning
an accidental, duplicated-by-hand invariant into one that is structurally
guaranteed and regression-tested, so a sixth command screen added later can't
silently drift.

## Decision: Deduplicate the shared shortcut set into one constant

**Decision**: Add `src/ome_zarr_tools/tui/shortcuts.py` exporting
`shared_bindings(primary_label: str = "Run") -> list[Binding]`, returning the
canonical six `(key, action, label)` bindings in the fixed order established
above. Each of the five screens replaces its hand-written prefix with
`*shared_bindings()` (or `*shared_bindings(primary_label="Save")` for
`ConfigScreen`), keeping any screen-specific extra binding
(`InspectScreen`'s `f9`) appended afterward, unchanged.

**Rationale**: The five lists are already identical in substance; leaving
them as five separately hand-maintained copies is exactly the kind of
duplication the project's own code-quality principle asks to remove, and it
is the direct, minimal mechanism that makes FR-001/FR-003 hold *by
construction* rather than by every future editor remembering to copy the
right six lines in the right order. This is not speculative — it's sized
exactly to the present, concrete duplication and the spec's explicit
consistency requirement, nothing more (no base-class hierarchy, no runtime
registry).

**Alternatives considered**:
- *Leave all five `BINDINGS` lists as separate literals; add only a test that
  compares them.* Rejected: a test alone documents the invariant but doesn't
  prevent drift at the point of change — a sixth screen (or an edit to one of
  the five) can still silently diverge and only be caught if someone
  remembers to run that specific test. Given the fix is already this small,
  removing the duplication outright is barely more work and is the more
  durable fix.
- *A shared base `Screen` subclass (e.g. `CommandScreenBase`) owning
  `BINDINGS` plus common `action_copy`/`action_back`/`action_cancel`
  implementations.* Rejected as out of scope: the five screens' action
  *implementations* differ enough (different status panels, different
  copy-source data) that unifying them would be a much larger refactor than
  this feature asks for, and the spec's own Assumptions section explicitly
  scopes this feature to shortcut/structure consistency, not an
  implementation-sharing refactor.

## Decision: Remove `CommandFormScreen`'s invocation-preview Label

**Decision**: Delete `self._invocation_label`, its `compose()` yield,
`on_mount`'s call to `_refresh_invocation()`, the three
`on_input_changed`/`on_checkbox_changed`/`on_select_changed` handlers (whose
only job was refreshing that label), and `_refresh_invocation()` itself. Keep
`_invocation_text()` unchanged — it's already a pure function of the current
field widgets, called on demand from `action_copy()`.

**Rationale**: Matches the pattern already proven correct in
`InspectScreen`/`ConfigScreen`/`FixMetadataScreen`/`MigrateScreen`, satisfies
FR-004/FR-005 exactly, and is a net deletion (no new state, no new widget) —
aligned with the code-quality principle against carrying dead code forward.

**Alternatives considered**:
- *Keep the widget but hide it (`display = False`) so the DOM structure stays
  parallel to before.* Rejected: keeps three now-pointless event handlers and
  a`Label` instance around for no behavioral benefit — exactly the kind of
  leftover the code-quality principle asks to avoid.

## Decision: Guard the invariant with a static-inspection test, not a full render

**Decision**: The regression test for shortcut-set parity (SC-001, SC-004)
inspects each screen class's `BINDINGS` class attribute directly (a plain
list comparison against `shared_bindings()`'s key/action pairs, ignoring the
allowed label override), rather than mounting every screen in a
`Pilot`/`App.run_test()` session and reading rendered `Footer` text.

**Rationale**: `BINDINGS` is the actual source of truth Textual's `Footer`
renders from; asserting on it directly is faster (no app/event-loop setup per
screen), deterministic (not dependent on terminal width/Footer's own
overflow/truncation logic, which is explicitly out of scope per the spec's
edge cases), and fails with a precise, readable diff (which key/action/order
mismatched) rather than a screen-diff to eyeball.

**Alternatives considered**:
- *Render each screen via `Pilot` and read the `Footer` widget's displayed
  key/label pairs.* Rejected as the primary test: slower, and couples the
  test to `Footer`'s own layout/overflow behavior, which this feature
  explicitly does not change or care about (see spec Edge Cases). Still
  useful as a smoke check that the app boots with the new `shortcuts.py`
  import wired correctly — kept as one lightweight existing-style
  `Pilot`-based test per screen (already how `test_interactive_tui.py` and
  `test_tui_screens.py` are structured), not a new mechanism.

## Testing approach (`Testing` field of Technical Context)

Unchanged from `002`: `pytest` + `pytest-asyncio`, Textual's
`App.run_test()`/`Pilot` for behavioral tests, plus the new static
`BINDINGS`-inspection test described above for the cross-screen invariant.
No new test infrastructure needed.
