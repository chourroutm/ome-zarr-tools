# Tasks: Consistent TUI Menus & Forms

**Input**: Design documents from `/specs/003-tui-menu-consistency/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/shortcut-contract.md, quickstart.md

**Tests**: Required — this project's constitution (`.specify/memory/constitution.md`, Principle II, NON-NEGOTIABLE) mandates a failing-then-passing regression test for every behavioral change.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project (Option 1, unchanged from `001`/`002`): `src/ome_zarr_tools/`, `tests/`.

---

## Phase 1: Setup

**Purpose**: Confirm the baseline is clean before touching anything.

- [X] T001 Run `ruff check src tests`, `ruff format --check src tests`, `mypy`, and `pytest` on the current `main` tip and confirm all pass, establishing a clean starting point (per constitution Quality Gates)

---

## Phase 2: Foundational

**Not applicable to this feature.** Per `plan.md`'s Constitution Check and `research.md`'s baseline audit, User Stories 1, 2, and 3 touch disjoint files/screens and have no shared blocking infrastructure to build first — each can start immediately after Phase 1.

---

## Phase 3: User Story 1 - One shortcut set to learn, everywhere (Priority: P1) 🎯 MVP

**Goal**: Every per-command screen's shared shortcuts (primary action, Copy, Copy & exit, Toggle log, Back, Cancel) come from one canonical source (`shared_bindings()`) instead of five independently hand-written lists, so future screens can't silently drift from the set `contracts/shortcut-contract.md` defines.

**Independent Test**: Run `tests/integration/test_tui_shortcuts.py` — it inspects the `BINDINGS` of `CommandFormScreen`, `InspectScreen`, `FixMetadataScreen`, `MigrateScreen`, and `ConfigScreen` directly and asserts the shared six-entry prefix matches `shared_bindings()` in key/action/order.

### Tests for User Story 1 ⚠️

> Write this test FIRST. It MUST fail (import error) until T003 exists.

- [X] T002 [P] [US1] Write `tests/integration/test_tui_shortcuts.py`: import `shared_bindings` from `src/ome_zarr_tools/tui/shortcuts.py` (does not exist yet — this import failing is the expected initial "red" state) and, for each of `CommandFormScreen`, `InspectScreen`, `FixMetadataScreen`, `MigrateScreen`, `ConfigScreen`, assert their `BINDINGS`' first six `(key, action)` pairs equal `shared_bindings()`'s, that `ConfigScreen`'s `f5` label is `"Save"` while its key/action match, and that `InspectScreen`'s `f9`/`switch_panel` entry comes after the shared six (contract rules 1-3)

### Implementation for User Story 1

- [X] T003 [US1] Create `src/ome_zarr_tools/tui/shortcuts.py` with `shared_bindings(primary_label: str = "Run") -> list[Binding]`, returning the six canonical `(key, action, label)` bindings from `contracts/shortcut-contract.md` in order: `f5`/`run`/`primary_label`, `f6`/`copy`/`"Copy"`, `f7`/`copy_and_exit`/`"Copy & exit"`, `f8`/`toggle_log`/`"Log"`, `escape`/`back`/`"Back to menu"`, `ctrl+c`/`cancel`/`"Cancel"`
- [X] T004 [P] [US1] In `src/ome_zarr_tools/tui/app.py`, replace `CommandFormScreen.BINDINGS`' hand-written list with `BINDINGS = [*shared_bindings()]`
- [X] T005 [P] [US1] In `src/ome_zarr_tools/tui/screens/inspect_screen.py`, replace `InspectScreen.BINDINGS`' hand-written list with `BINDINGS = [*shared_bindings(), Binding("f9", "switch_panel", "Switch panel")]`
- [X] T006 [P] [US1] In `src/ome_zarr_tools/tui/screens/metadata_screen.py`, replace both `FixMetadataScreen.BINDINGS` and `MigrateScreen.BINDINGS`' hand-written lists with `BINDINGS = [*shared_bindings()]`
- [X] T007 [P] [US1] In `src/ome_zarr_tools/tui/screens/config_screen.py`, replace `ConfigScreen.BINDINGS`' hand-written list with `BINDINGS = [*shared_bindings(primary_label="Save")]`
- [X] T008 [US1] Run `pytest tests/integration/test_tui_shortcuts.py` and confirm it now passes (depends on T003-T007); run the full suite (`pytest`) to confirm no existing TUI test regressed

**Checkpoint**: User Story 1 is fully functional and independently testable — every per-command screen's shared shortcuts are structurally guaranteed consistent.

---

## Phase 4: User Story 2 - Cleaner generic-form screens (Priority: P2)

**Goal**: `from_images`, `extract`, and `apply_mask` (all sharing `CommandFormScreen`) no longer render the live command-invocation-preview line; Copy and Copy & exit continue to place the exact, correct invocation on the clipboard.

**Independent Test**: Open (or headlessly mount, via `Pilot`) the `from_images`/`extract`/`apply_mask` form; confirm no invocation-preview widget is present; confirm `action_copy`/`action_copy_and_exit` still produce the correct clipboard content.

### Tests for User Story 2 ⚠️

> Update this test FIRST. It MUST fail against the current code (the widget still exists) until T010 is done.

- [X] T009 [P] [US2] Update `tests/integration/test_interactive_tui.py`'s `CommandFormScreen` tests: assert `pilot.app.screen.query("#invocation")` (or equivalent) returns no widgets after mounting/editing fields, while `app.screen._invocation_text()` and a Copy/Copy & exit clipboard-content assertion (contract rule 5) still pass

### Implementation for User Story 2

- [X] T010 [US2] In `src/ome_zarr_tools/tui/app.py`'s `CommandFormScreen`, delete `self._invocation_label` (and its `compose()` yield), `on_mount`'s call to `_refresh_invocation()`, the `on_input_changed`/`on_checkbox_changed`/`on_select_changed` handlers (whose only purpose was refreshing that label), and `_refresh_invocation()` itself; leave `_invocation_text()` unchanged, still called from `action_copy()`/`action_copy_and_exit()`
- [X] T011 [US2] Run `pytest tests/integration/test_interactive_tui.py` and confirm the updated tests pass; run the full suite to confirm no regression in `extract`/`apply_mask` behavior (they share `CommandFormScreen`, no per-command code path)

**Checkpoint**: User Stories 1 AND 2 both work independently — shortcuts are consistent, and the three generic-form commands no longer show the preview panel.

---

## Phase 5: User Story 3 - Same structural skeleton across all screens (Priority: P3)

**Goal**: Every command screen provably has exactly one header, one status/log region directly above the footer, and one footer; the command menu shares the same header/footer chrome without needing a status/log region.

**Independent Test**: Run the new structural test below against all screen classes; per `research.md`'s baseline audit this is expected to already pass (the `#bottom-bar` wrapper pattern from `002` already established this), so this story is primarily a regression guard against future drift, not a code change.

### Tests for User Story 3 ⚠️

- [X] T012 [P] [US3] Add `test_all_command_screens_share_the_same_structural_skeleton` to `tests/integration/test_tui_screens.py` (or a new `tests/integration/test_tui_structure.py`): for `CommandFormScreen`, `InspectScreen`, `FixMetadataScreen`, `MigrateScreen`, `ConfigScreen`, mount each via `Pilot` and assert exactly one `Header`, exactly one `Footer`, and exactly one status/log region (`StatusPanel`) mounted directly above the footer; separately assert `CommandMenuScreen` has exactly one `Header` and one `Footer` (contract rule 4)

### Implementation for User Story 3

- [X] T013 [US3] Run T012's new test; if it fails for any screen (unexpected per `research.md`, but not guaranteed), fix that screen's `compose()`/CSS to match the `#bottom-bar` wrapper pattern already used by the other screens — otherwise, no code change is needed and this task is closed as a verification-only pass

**Checkpoint**: All three user stories are independently functional; the TUI's menus and forms are consistent per the spec.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide validation and documentation now that all three stories are done.

- [X] T014 [P] Run `ruff check src tests`, `ruff format --check src tests`, `mypy`, and `pytest` (full suite) and confirm all pass (constitution Quality Gates)
- [X] T015 Walk through `quickstart.md`'s three manual scenarios (shortcut consistency, no command-preview panel, structural skeleton) in a live `interactive --tui` session
- [X] T016 [P] Update `README.md`'s `interactive --tui` section (currently states "the equivalent CLI invocation is always shown live above the footer" — no longer true after US2) to describe Copy/Copy & exit as computing the invocation on demand rather than displaying it live

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: N/A — nothing blocks the user stories (see above).
- **User Stories (Phase 3-5)**: Each depends only on Phase 1 (clean baseline). They touch disjoint files (`shortcuts.py`+screen `BINDINGS` for US1; `CommandFormScreen`'s preview widget for US2; a new structural test for US3) and can proceed in parallel or in any order.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies on US2/US3.
- **User Story 2 (P2)**: No dependencies on US1/US3 — independent file (`CommandFormScreen`'s preview widget vs. its `BINDINGS`, which US1 also touches in the same class; sequence T004 and T010 in either order, they don't conflict since they touch different methods/attributes of `CommandFormScreen`).
- **User Story 3 (P3)**: No dependencies on US1/US2 — purely additive test, expected to pass without any implementation change.

### Within Each User Story

- Test task(s) written/updated before the corresponding implementation task(s), per constitution Principle II.
- Verify (run tests) task after implementation.

### Parallel Opportunities

- T002 (US1 test) can be written in parallel with T009 (US2 test) and T012 (US3 test) — different files.
- T004, T005, T006, T007 (US1's four screen updates) can run in parallel once T003 exists — four different files.
- T014 and T016 (Polish) can run in parallel — different concerns (test/lint run vs. doc edit).

---

## Parallel Example: User Story 1

```bash
# After T003 (shortcuts.py) exists, launch all four screen updates together:
Task: "Update CommandFormScreen.BINDINGS in src/ome_zarr_tools/tui/app.py"
Task: "Update InspectScreen.BINDINGS in src/ome_zarr_tools/tui/screens/inspect_screen.py"
Task: "Update FixMetadataScreen/MigrateScreen.BINDINGS in src/ome_zarr_tools/tui/screens/metadata_screen.py"
Task: "Update ConfigScreen.BINDINGS in src/ome_zarr_tools/tui/screens/config_screen.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 3: User Story 1 (T002-T008).
3. **STOP and VALIDATE**: `pytest tests/integration/test_tui_shortcuts.py` passes; full suite green.
4. This alone satisfies the spec's highest-priority story and is safe to ship on its own.

### Incremental Delivery

1. Setup → Phase 1 done.
2. Add User Story 1 (shortcut consistency) → validate independently.
3. Add User Story 2 (remove preview panel) → validate independently.
4. Add User Story 3 (structural-skeleton guard test) → validate independently.
5. Polish (Phase 6): full quality gates + README update.

---

## Notes

- [P] tasks touch different files with no unmet dependencies.
- All three user stories are independent — no cross-story integration work is needed, unlike the template's generic example.
- Every implementation task in US1/US2 is preceded by a test task that fails before the change (constitution Principle II, NON-NEGOTIABLE).
- Commit only when explicitly asked, as new commits — never amend (constitution Principle III).
