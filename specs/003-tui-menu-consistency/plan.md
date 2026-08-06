# Implementation Plan: Consistent TUI Menus & Forms

**Branch**: `main` (no dedicated feature branch — this repo ships features 001/002 directly on `main`, per existing convention) | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-tui-menu-consistency/spec.md`

## Summary

Make the Textual TUI's per-command shortcut set consistent *by construction*
instead of by five independently hand-written, currently-identical
`BINDINGS` lists, and remove the live command-invocation-preview panel from
the one screen that still renders it (`CommandFormScreen`, shared by
`from_images`/`extract`/`apply_mask`). `research.md`'s baseline audit found
the shortcut ordering/keys the spec asks for already match today, by
coincidence — so the substantive work is (a) extracting that shared list
into one `shared_bindings()` constant all five screens use, guarded by a new
static regression test, and (b) deleting `CommandFormScreen`'s now-redundant
preview `Label` and its refresh wiring, matching the pattern the four
specialized screens already use (compute the invocation on demand for
Copy/Copy & exit; never render it).

## Technical Context

**Language/Version**: Python ≥3.10 (unchanged)

**Primary Dependencies**: `textual>=8.0` (unchanged). No new dependencies.

**Storage**: N/A — no persisted state involved.

**Testing**: `pytest` + `pytest-asyncio` (unchanged), Textual's
`App.run_test()`/`Pilot` for behavioral checks plus one new static
`BINDINGS`-inspection test (no app boot required) for the cross-screen
shortcut invariant — see `research.md`.

**Target Platform**: Unchanged — Linux/macOS terminal, `--tui` requires an
attached interactive terminal.

**Project Type**: Single project — CLI tool (Option 1, unchanged)

**Performance Goals**: N/A — no behavior affecting runtime performance;
existing worker-thread execution model (from `002`) is untouched.

**Constraints**: Every existing TUI test in `tests/integration/` (footer
shortcuts, worker execution, screens, diff previews) MUST keep passing
unchanged in behavior — this feature reorganizes how `BINDINGS` are declared
and removes one dead widget, it does not change any command's runtime
behavior or CLI output.

**Scale/Scope**: 1 command-menu screen + 7 per-command screens
(`from_images`, `extract`, `apply_mask` sharing `CommandFormScreen`;
`fix_metadata`, `migrate`, `inspect`, `config` each with their own screen).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Code Quality & Best Practice**: This plan is a net *deletion* of
  duplicated/dead code (five hand-written `BINDINGS` lists → one shared
  constant; a dead preview `Label` and its refresh handlers). No new
  configuration, flags, or speculative abstraction is introduced —
  `shared_bindings()` is a plain function sized to the one, concrete,
  present duplication. **PASS**.
- **II. Test-First Development**: Both behavior changes (shortcut-set
  invariant, preview-panel removal) get a new automated regression test
  before/alongside the change (`test_tui_shortcuts.py` for the former; an
  update to `test_interactive_tui.py`'s `CommandFormScreen` tests for the
  latter, asserting no preview widget exists while `_invocation_text()`
  still drives Copy/Copy & exit correctly). **PASS**.
- **III. Deliberate Commit Discipline**: No commits made yet for this
  feature; the eventual commit will be new (never amended), per standing
  practice. Not a design-time gate — **N/A at planning time**, tracked at
  implementation/commit time.

No violations. `Complexity Tracking` is empty — nothing to justify.

## Project Structure

### Documentation (this feature)

```text
specs/003-tui-menu-consistency/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── shortcut-contract.md   # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── ome_zarr_tools/
    └── tui/
        ├── shortcuts.py            # NEW: shared_bindings(primary_label="Run")
        │                            # -> list[Binding]; the six-entry canonical
        │                            # shared shortcut set (research.md)
        ├── app.py                  # MODIFIED: CommandFormScreen.BINDINGS built
        │                            # from shared_bindings(); _invocation_label,
        │                            # _refresh_invocation, and the three
        │                            # on_*_changed handlers that only refreshed
        │                            # it are deleted. _invocation_text() unchanged,
        │                            # still used by action_copy/action_copy_and_exit.
        └── screens/
            ├── inspect_screen.py     # MODIFIED: BINDINGS = [*shared_bindings(),
            │                          # Binding("f9", "switch_panel", "Switch panel")]
            ├── metadata_screen.py    # MODIFIED: both FixMetadataScreen and
            │                          # MigrateScreen's BINDINGS built from
            │                          # shared_bindings()
            └── config_screen.py      # MODIFIED: BINDINGS = [*shared_bindings(
                                       # primary_label="Save")]

tests/
└── integration/
    ├── test_tui_shortcuts.py         # NEW: static BINDINGS-inspection test
    │                                   # (contracts/shortcut-contract.md rules 1-3)
    │                                   # against all five per-command screen classes
    └── test_interactive_tui.py       # MODIFIED: CommandFormScreen tests updated
                                        # to assert no invocation-preview widget is
                                        # mounted, while Copy/Copy & exit clipboard
                                        # content (via _invocation_text()) is
                                        # unchanged (contract rule 5)
```

**Structure Decision**: Single-project CLI (Option 1), unchanged from `001`
and `002`. This feature adds exactly one new module (`tui/shortcuts.py`) and
one new test module; every other change is an in-place edit to existing
`tui/` files. No new top-level packages, no changes outside `src/ome_zarr_tools/tui/`
and `tests/integration/`.

## Complexity Tracking

*No constitution violations — table intentionally empty.*
