---

description: "Task list for Browse picker directory-name click selects and closes"
---

# Tasks: Browse picker directory-name click selects and closes

**Input**: Design documents from `/specs/006-browse-picker-directory-click/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/browse-picker-contract.md, quickstart.md

**Tests**: Included and REQUIRED — this project's constitution, Principle II ("Test-First Development"), is non-negotiable. Every task below that changes behavior is preceded by a failing-test task for the same behavior.

**Organization**: This feature is a single user story (P1) — no Setup/Foundational phases are needed; the change lands in one already-existing file (constitution Principle I: prefer editing existing modules).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files/regions, no dependency on an unfinished task)
- **[Story]**: Which user story this task belongs to

## Phase 1: User Story 1 - Pick an output folder by clicking its name (Priority: P1) 🎯 MVP

**Goal**: Clicking a directory's name in the Browse popup dismisses the popup and fills the field for `only="any"` fields (e.g. `from_images`'s OUTPUT_ZARR, `extract`'s `--output`), exactly as it already does for `only="dir"` fields.

**Independent Test**: Open `from_images`'s OUTPUT_ZARR Browse popup, click directly on a folder's name (not its expand/collapse icon), and confirm the popup closes and OUTPUT_ZARR is filled with that folder's path.

### Tests for User Story 1 ⚠️ write first, confirm they FAIL

- [X] T001 [P] [US1] Failing test: `from_images`'s OUTPUT_ZARR Browse popup (`only="any"`) dismisses and fills the field when a directory is selected (post `DirectoryTree.DirectorySelected`, mirroring the existing `stack_dir`/`only="dir"` full-flow test's shape) — in `tests/integration/test_tui_browse_picker.py`
- [X] T002 [P] [US1] Failing test: same-shape regression for `extract`'s `--output` field (also `only="any"`) — same file, confirms the fix lives in the shared component per the spec's clarification, not a `from_images`-only special case
- [X] T003 [P] [US1] Failing test: a field restricted to files only (`only="file"`, e.g. `from_images`'s `--vol_file`) still does NOT dismiss when a directory is selected — regression guard for FR-005, since the fix refactors the same guard that must keep excluding this case — same file (this one already passed against the unfixed code, as expected -- existing behavior, not new)

### Implementation for User Story 1

- [X] T004 [US1] `BrowsePickerScreen.on_directory_tree_directory_selected()` in `src/ome_zarr_tools/tui/screens/browse_screen.py`: change the `if self.only == "dir": self.dismiss(event.path)` body to `if self.only == "file": return` followed by `self.dismiss(event.path)`, mirroring the sibling `on_directory_tree_file_selected()` handler's existing guard shape (depends on T001-T003 existing and failing)

**Checkpoint**: User Story 1 fully functional — run `pytest tests/integration/test_tui_browse_picker.py -q` to validate independently.

---

## Phase 2: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates — no further behavior changes.

- [X] T005 `ruff check src tests`, `ruff format --check src tests`, `mypy src` all clean
- [X] T006 Full `pytest` suite green (including the pre-existing suite, unaffected by this feature) — run as 6 sequential batches by file (contract/, non-TUI integration, 3× TUI integration groups, unit/), per this project's established practice for this HPC environment (a full single-process run has previously aborted under resource pressure). All 6 batches passed (188 tests: 185 pre-existing + 3 new).
- [ ] T007 [P] Run `quickstart.md`'s manual walkthrough in a real terminal, covering both `from_images`'s OUTPUT_ZARR and `extract`'s `--output`, plus confirming the expand/collapse icon and the already-working `only="dir"` fields are unchanged

---

## Dependencies & Execution Order

- T001-T003 can be written in parallel — different assertions, same existing test file — but must all be committed/failing before T004 starts (constitution Principle II).
- T004 depends on T001-T003 existing and failing.
- Phase 2 depends on Phase 1.

## Parallel Example: User Story 1

```bash
# Tests (after confirming they fail against the current, unfixed handler):
Task: "Failing test: OUTPUT_ZARR (only=any) directory-name click dismisses and fills"
Task: "Failing test: extract --output (only=any) directory-name click dismisses and fills"
Task: "Failing test: vol_file (only=file) directory-name click stays a no-op"

# Implementation (after T001-T003 land):
Task: "Fix BrowsePickerScreen.on_directory_tree_directory_selected() guard"
```

## Implementation Strategy

Single-story MVP: T001-T004 delivers the entire feature (spec has only one
user story). Phase 2 is quality-gate confirmation, not new behavior.
