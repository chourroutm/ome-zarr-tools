# Implementation Plan: TUI Visual Redesign

**Branch**: `main` (no dedicated feature branch — this repo ships features 001/002/003 directly on `main`, per existing convention) | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-tui-visual-redesign/spec.md`

## Summary

Redesign the Textual TUI's visual surface across 5 user stories: a static
ASCII logo + 3-line Rich `OptionList` entries on the command menu (US1);
required/optional field-group frames on every command
screen (US2); human-readable field labels with CLI tokens unchanged (US3);
a `ModalScreen`-based directory-tree "Browse" picker beside every path
field (US4); and a Bootstrap-input-group-style colored add-on for
`gs://`/`gcs://`/`s3://`/`az://`/`abfs://`/`http://`/`https://` path
prefixes, with autocomplete suppressed while shown (US5). `research.md`'s
baseline audit found the specialized screens (`inspect`/`fix_metadata`/
`migrate`/`config`) hand-build their own fixed fields rather than iterating
`click.Parameter`s like `CommandFormScreen` does — so US2/US3's frame
grouping and label casing need one shared primitive
(`fields.py`'s `FieldSpec` + `build_field_frames()`) that both paths feed
into, mirroring `003`'s `shared_bindings()` pattern (one small shared
constant/function, not a deeper class-hierarchy refactor).

## Technical Context

**Language/Version**: Python ≥3.10 (unchanged)

**Primary Dependencies**: `textual>=8.0`, `textual-autocomplete>=4.0`
(unchanged). No new dependencies — `OptionList`, `DirectoryTree`,
`ModalScreen`, and `Button` are all part of
`textual` already installed; Rich renderables (`rich.console.Group`,
`rich.text.Text`) come from `rich`, already a transitive dependency of
`textual`.

**Storage**: N/A — no persisted state; the Browse picker reads the local
filesystem read-only, same access pattern `SafePathAutoComplete` already
uses.

**Testing**: `pytest` + `pytest-asyncio` (unchanged), Textual's
`App.run_test()`/`Pilot`. New coverage per `research.md`'s Testing
approach: `ModalScreen` push/dismiss round-trips, `Input.Changed`-driven
add-on state-machine transitions, and static assertions on `Option.prompt`
Rich content — no new test infrastructure.

**Target Platform**: Unchanged — Linux/macOS terminal, `--tui` requires an
attached interactive terminal.

**Project Type**: Single project — CLI tool (Option 1, unchanged)

**Performance Goals**: N/A — no behavior affecting runtime performance of
the underlying CLI commands; the add-on's `Input.Changed` handler and the
menu's Rich-content construction are cheap, synchronous, per-keystroke/
per-render operations with no I/O.

**Constraints**: Every existing TUI test (`002`'s execution/status tests,
`003`'s shortcut/structure tests) MUST keep passing unchanged in behavior —
this feature changes field layout, labels, and widget composition, not the
shortcut set or the header/status-log/footer skeleton `003` established.
`widget_value_to_tokens()`'s CLI-token output MUST be byte-for-byte
unaffected by any of this feature's changes (FR-007/FR-018, `003`'s own
Constitution-driven regression-test discipline extended here).

**Scale/Scope**: 1 command-menu screen + 5 per-command screen classes
(`CommandFormScreen` shared by 3 commands; `InspectScreen`,
`FixMetadataScreen`, `MigrateScreen`, `ConfigScreen`); a new modal screen
(`BrowsePickerScreen`); up to 7 recognized remote path schemes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Code Quality & Best Practice**: Every new construct
  (`FieldSpec`/`build_field_frames`, `Logo`, `BrowsePickerScreen`/
  `SafeDirectoryTree`, the add-on `Horizontal` composition,
  `REMOTE_SCHEME_COLORS`) maps directly to an explicit FR — none is
  speculative. `build_field_frames()` specifically *removes* the
  alternative of five screens independently reimplementing the same
  grouping logic, the same "one shared primitive over duplicated
  per-screen code" reasoning `003` already established for shortcuts.
  **PASS**.
- **II. Test-First Development**: Every behavior change gets a paired
  regression test per `research.md`'s Testing approach and
  `contracts/visual-design-contract.md`'s "Who verifies" section,
  written/updated before the corresponding implementation, per this
  project's standing practice. **PASS**.
- **III. Deliberate Commit Discipline**: N/A at planning time — no commits
  made yet for this feature; tracked at implementation/commit time per
  standing practice.

No violations. `Complexity Tracking` is empty — this feature is large in
FR *count* (5 user stories) but each FR maps to one small, concrete,
directly-requested piece of UI; nothing here is complexity added beyond
what was explicitly asked for.

## Project Structure

### Documentation (this feature)

```text
specs/004-tui-visual-redesign/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── visual-design-contract.md   # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── ome_zarr_tools/
    └── tui/
        ├── logo.py                  # NEW: LOGO ASCII-art constant, Logo(Static)
        │                             # widget with resize-reactive display (US1)
        ├── app.py                   # MODIFIED: CommandMenuScreen mounts Logo,
        │                             # builds 3-line Rich Option prompts per
        │                             # command (US1); CommandFormScreen builds
        │                             # FieldSpecs per click.Parameter and calls
        │                             # build_field_frames() instead of a flat
        │                             # field loop (US2/US3)
        ├── fields.py                 # MODIFIED: field_label() -> human-readable
        │                             # casing (US3); NEW FieldSpec dataclass,
        │                             # build_field_frames() (US2); NEW
        │                             # REMOTE_SCHEME_COLORS table, add-on
        │                             # Horizontal composition + Input.Changed
        │                             # handler (US5); NEW Browse Button wiring
        │                             # per path field (US4)
        └── screens/
            ├── browse_screen.py      # NEW: BrowsePickerScreen(ModalScreen[Path |
            │                          # None]), SafeDirectoryTree (US4)
            ├── inspect_screen.py      # MODIFIED: own FieldSpec list ->
            │                          # build_field_frames()
            ├── metadata_screen.py     # MODIFIED: same, for FixMetadataScreen and
            │                          # MigrateScreen
            └── config_screen.py       # MODIFIED: same, for ConfigScreen

tests/
└── integration/
    ├── test_tui_visual_design.py     # NEW: static assertions per
    │                                   # contracts/visual-design-contract.md --
    │                                   # menu entry Rich content (US1), frame
    │                                   # membership/order (US2), label casing
    │                                   # (US3)
    ├── test_tui_browse_picker.py      # NEW: ModalScreen push/dismiss round-trip,
    │                                   # filter_paths dir/file constraint,
    │                                   # cancel-leaves-field-unchanged (US4)
    └── test_tui_remote_addon.py       # NEW: type/backspace state-machine
                                        # transitions for all 4 color groups,
                                        # CLI-token equivalence (US5)
```

**Structure Decision**: Single-project CLI (Option 1), unchanged from
`001`-`003`. One new module (`tui/logo.py`), one new screen
(`tui/screens/browse_screen.py`), and three new test modules; every other
change is an in-place edit to existing `tui/` files. No new top-level
packages, no changes outside `src/ome_zarr_tools/tui/` and
`tests/integration/`.

## Complexity Tracking

*No constitution violations — table intentionally empty.*
