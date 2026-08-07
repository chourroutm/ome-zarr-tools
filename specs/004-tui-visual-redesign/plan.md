# Implementation Plan: TUI Visual Redesign

**Branch**: `main` (no dedicated feature branch — this repo ships features 001/002/003 directly on `main`, per existing convention) | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-tui-visual-redesign/spec.md`

## Summary

Redesign the Textual TUI's visual surface, and its run/navigation flow,
across 7 user stories: a static ASCII logo + 3-line Rich `OptionList`
entries on the command menu (US1); required/optional field-group frames on
every command screen, with a tall red/tall blue border per group and a
live still-empty-count subtitle on the required frame (US2);
human-readable field labels with CLI tokens unchanged (US3); a
`ModalScreen`-based directory-tree "Browse" picker beside every path field
(US4); a Bootstrap-input-group-style colored add-on for
`gs://`/`gcs://`/`s3://`/`az://`/`abfs://`/`http://`/`https://` path
prefixes, with autocomplete suppressed while shown (US5); a titled,
gold-bordered Command Identity frame (name + description) shown at the top
of every prep screen *and* reused at the top of that command's Result
screen (US6); and, on Run, immediate navigation to a dedicated Command
Result screen showing a live progress bar/sparkline (the existing
`StatusPanel`, relocated) while the command runs, then that command's
specific outcome once it finishes — one shared `CommandResultScreen` base
class plus a per-command subclass — instead of staying on the prep screen
(US7). US7 also adds a Restore Defaults shortcut (`F4`) that reloads a
prep screen via `App.switch_screen()` rather than resetting fields
individually, and renames the Result screen's return-to-prep binding to
"Back to form" (a scoped, screen-local exception to `shared_bindings()`'s
otherwise-fixed label, per research.md).
`research.md`'s baseline audit found the specialized screens
(`inspect`/`fix_metadata`/`migrate`/`config`) hand-build their own fixed
fields rather than iterating `click.Parameter`s like `CommandFormScreen`
does — so US2/US3/US6's frame grouping, label casing, and identity frame
need one shared primitive (`fields.py`'s `FieldSpec` + `build_field_frames
()` + `build_identity_frame()`) that both paths feed into, mirroring
`003`'s `shared_bindings()` pattern (small shared constants/functions, not
a deeper class-hierarchy refactor) — US7's result screens are the one
place this feature does introduce a small class hierarchy
(`CommandResultScreen` base + 5 subclasses), since the differences there
are in *what's composed*, not a reusable data transform; `StatusPanel`
(spec 002 US5) is reused wholesale for the Result screen's pending-state
progress display, not reimplemented.

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
add-on state-machine transitions, static assertions on `Option.prompt`
Rich content, and — for US7 — `Pilot.press("f5")` on a filled-in prep
screen followed by asserting `app.screen` becomes the expected
`CommandResultScreen` subclass *immediately* (before the worker
resolves), showing the identity frame and a pending `StatusPanel`; then,
after the worker resolves, asserting that same screen instance now shows
the expected success/failure state and command-specific content; plus a
required-field-empty case asserting no navigation occurred, a
second-Run-while-pending case asserting no second screen is constructed,
and a Restore Defaults case asserting `app.screen` becomes a new instance
with every field back to its opening value (no-op while disabled during a
run). No new test infrastructure beyond what `App.run_test()`/`Pilot`
already provide.

**Target Platform**: Unchanged — Linux/macOS terminal, `--tui` requires an
attached interactive terminal.

**Project Type**: Single project — CLI tool (Option 1, unchanged)

**Performance Goals**: N/A — no behavior affecting runtime performance of
the underlying CLI commands; the add-on's `Input.Changed` handler and the
menu's Rich-content construction are cheap, synchronous, per-keystroke/
per-render operations with no I/O.

**Constraints**: Every existing TUI test (`002`'s execution/status tests,
`003`'s shortcut/structure tests) MUST keep passing unchanged in behavior,
**except** that Run's behavior itself changes by design (US7): tests
asserting "stays on the same screen after pressing Run" must be updated to
assert "navigates to the matching Result screen immediately" instead —
this is the one deliberate behavior change in an otherwise visual-only
feature, and it now spans the *entire* run (from Run-press through
completion), not just its aftermath, since `002`'s own
progress-bar/sparkline `StatusPanel` display relocates from the prep
screen to the newly-pushed Result screen for the duration of that run
(the prep screen's own `StatusPanel` keeps working exactly as before for
Copy/Copy & exit's log-append behavior — it's just not driven by Run
anymore). `execution.py`'s `on_done`/`on_log` mechanism itself is
unchanged — only *which screen's widgets* its callbacks target. The
shortcut set is unchanged except for two additive, scoped changes: a new
Restore Defaults binding (`F4`) on every prep screen, and the Result screen's own
`escape` binding showing "Back to form" instead of `shared_bindings()`'s
generic "Back to menu" label (key and action unchanged, per research.md's
binding-override decision). `widget_value_to_tokens()`'s CLI-token output
MUST be byte-for-byte unaffected by any of this feature's changes
(FR-007/FR-018, `003`'s own Constitution-driven regression-test
discipline extended here).

**Scale/Scope**: 1 command-menu screen + 5 per-command prep-screen classes
(`CommandFormScreen` shared by 3 commands; `InspectScreen`,
`FixMetadataScreen`, `MigrateScreen`, `ConfigScreen`); a new modal screen
(`BrowsePickerScreen`); a new `CommandResultScreen` base class plus 5
per-command Result subclasses (`GenericResultScreen`,
`InspectResultScreen`, `FixMetadataResultScreen`, `MigrateResultScreen`,
`ConfigResultScreen`); up to 7 recognized remote path schemes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Code Quality & Best Practice**: Every new construct
  (`FieldSpec`/`build_field_frames`, `build_identity_frame`, `Logo`,
  `BrowsePickerScreen`/`SafeDirectoryTree`, the add-on `Horizontal`
  composition, `REMOTE_SCHEME_COLORS`, `CommandResultScreen` + its 5
  subclasses, `action_restore_defaults()`) maps directly to an explicit
  FR — none is speculative. `build_field_frames()`/`build_identity_frame()`
  specifically *remove* the alternative of five screens independently
  reimplementing the same grouping/identity logic, the same "one shared
  primitive over duplicated per-screen code" reasoning `003` already
  established for shortcuts. `CommandResultScreen` reuses `tui/status.py`'s
  existing `StatusPanel` wholesale for its progress display rather than
  adding a second progress-indicator implementation, and Restore Defaults
  reuses Textual's own built-in `App.switch_screen()` rather than a new
  per-field value-tracking mechanism — both directly "prefer editing
  existing modules over adding new abstractions."
  `CommandResultScreen` is the one genuine class hierarchy this feature
  adds; it's sized to the concrete, present need (5 commands, one shared
  chrome, 5 different result contents) rather than a speculative plugin
  system. **PASS**.
- **II. Test-First Development**: Every behavior change gets a paired
  regression test per `research.md`'s Testing approach and
  `contracts/visual-design-contract.md`'s "Who verifies" section,
  written/updated before the corresponding implementation, per this
  project's standing practice. **PASS**.
- **III. Deliberate Commit Discipline**: N/A at planning time — no commits
  made yet for this feature; tracked at implementation/commit time per
  standing practice.

No violations. `Complexity Tracking` is empty — this feature is large in
FR *count* (7 user stories) but each FR maps to one small, concrete,
directly-requested piece of UI or navigation change; nothing here is
complexity added beyond what was explicitly asked for.

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
        │                             # field loop (US2/US3); yields
        │                             # build_identity_frame() first (US6);
        │                             # gains action_restore_defaults() bound to F4,
        │                             # action_run() pushes GenericResultScreen
        │                             # immediately, drives it via begin()/
        │                             # finish(), guards against a second
        │                             # pending run (US7)
        ├── fields.py                 # MODIFIED: field_label() -> human-readable
        │                             # casing (US3); NEW FieldSpec dataclass,
        │                             # build_field_frames() -- tall red/tall blue
        │                             # borders, live required-count
        │                             # border_subtitle (US2); NEW
        │                             # build_identity_frame() -- gold round
        │                             # border (US6); NEW REMOTE_SCHEME_COLORS
        │                             # table, add-on Horizontal composition +
        │                             # Input.Changed handler (US5); NEW Browse
        │                             # Button wiring per path field (US4)
        ├── status.py                 # UNCHANGED: StatusPanel reused as-is,
        │                             # embedded in CommandResultScreen (US7)
        └── screens/
            ├── browse_screen.py      # NEW: BrowsePickerScreen(ModalScreen[Path |
            │                          # None]), SafeDirectoryTree (US4)
            ├── result_screen.py      # NEW: CommandResultScreen(Screen[None])
            │                          # base -- identity frame, embedded
            │                          # StatusPanel, begin()/finish() pending<->
            │                          # finished transition, "Back to form"
            │                          # binding override -- + GenericResultScreen
            │                          # (US7)
            ├── inspect_screen.py      # MODIFIED: own FieldSpec list ->
            │                          # build_field_frames(), identity frame
            │                          # (US6); action_restore_defaults() (US7); NEW
            │                          # InspectResultScreen, action_run() pushes
            │                          # it immediately (US7)
            ├── metadata_screen.py     # MODIFIED: same, for FixMetadataScreen and
            │                          # MigrateScreen; action_restore_defaults() (US7); NEW
            │                          # FixMetadataResultScreen,
            │                          # MigrateResultScreen (US7)
            └── config_screen.py       # MODIFIED: same, for ConfigScreen;
                                        # action_restore_defaults() (US7); NEW
                                        # ConfigResultScreen (US7)

tests/
└── integration/
    ├── test_tui_visual_design.py     # NEW: static assertions per
    │                                   # contracts/visual-design-contract.md --
    │                                   # frame membership/order (US2), label
    │                                   # casing + wrap-not-truncate (US3),
    │                                   # identity frame content (US6). Menu
    │                                   # entry Rich content (US1) already has
    │                                   # its own tests (test_tui_logo.py,
    │                                   # test_tui_menu.py)
    ├── test_tui_browse_picker.py      # NEW: ModalScreen push/dismiss round-trip,
    │                                   # filter_paths dir/file constraint,
    │                                   # cancel-leaves-field-unchanged (US4)
    ├── test_tui_remote_addon.py       # NEW: type/backspace state-machine
    │                                   # transitions for all 4 color groups,
    │                                   # CLI-token equivalence (US5)
    └── test_tui_result_screen.py      # NEW: Run navigates to the correct
                                        # CommandResultScreen subclass
                                        # immediately (pending state, identity
                                        # frame + StatusPanel), then to the
                                        # correct success/failure content once
                                        # finished, per command; blocked Run
                                        # navigates nowhere; a second Run while
                                        # pending re-navigates instead of
                                        # duplicating; "Back to form" returns to
                                        # the prep screen unchanged from either
                                        # state; Restore Defaults reloads via
                                        # switch_screen(), fields show opening
                                        # values, no-ops while disabled (US7)
```

**Structure Decision**: Single-project CLI (Option 1), unchanged from
`001`-`003`. Two new modules (`tui/logo.py`, `tui/screens/result_screen.py`),
one new screen (`tui/screens/browse_screen.py`), and four new test modules;
every other change is an in-place edit to existing `tui/` files. No new
top-level packages, no changes outside `src/ome_zarr_tools/tui/` and
`tests/integration/`.

## Complexity Tracking

*No constitution violations — table intentionally empty.*
