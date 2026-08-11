---

description: "Task list for Reliable Copy & Exit"
---

# Tasks: Reliable Copy & Exit

**Input**: Design documents from `/specs/005-reliable-copy-exit/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/copy-exit-contract.md, quickstart.md

**Tests**: Included and REQUIRED — this project's constitution, Principle II ("Test-First Development"), is non-negotiable. Every task below that changes behavior is preceded by a failing-test task for the same behavior.

**Organization**: This feature is a single user story (P1) — no Setup/Foundational phases are needed; every change lands in an already-existing file (constitution Principle I: prefer editing existing modules).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files/regions, no dependency on an unfinished task)
- **[Story]**: Which user story this task belongs to

## Phase 1: User Story 1 - Always able to retrieve the command after Copy & exit (Priority: P1) 🎯 MVP

**Goal**: Every per-command screen's "Copy & exit" prints the exact CLI invocation to the real terminal after the app exits, in addition to the existing (often-silently-failing) clipboard-copy attempt.

**Independent Test**: On any per-command screen, fill in fields, press "Copy & exit" (`F7`), and confirm — once the app exits — the terminal shows the exact CLI invocation as plain text, regardless of clipboard/OSC-52 support.

### Tests for User Story 1 ⚠️ write first, confirm they FAIL

- [X] T001 [P] [US1] Failing test: `CommandFormScreen.action_copy_and_exit()` exits `App.run_test()` with the invocation string as the result (not `None`) — in `tests/integration/test_tui_copy_exit.py` (new)
- [X] T002 [P] [US1] Failing test: `InspectScreen.action_copy_and_exit()` exits with the invocation string as the result — same file
- [X] T003 [P] [US1] Failing test: `fix_metadata`'s/`migrate`'s Form screens (`_BaseMetadataScreen.action_copy_and_exit()`) exit with the invocation string as the result — same file
- [X] T004 [P] [US1] Failing test: `fix_metadata`'s/`migrate`'s Confirm screens (`_BaseConfirmScreen.action_copy_and_exit()`, spec 004 US8) exit with the invocation string as the result — same file
- [X] T005 [P] [US1] Failing test: `ConfigScreen.action_copy_and_exit()` exits with the invocation string as the result — same file
- [X] T006 [P] [US1] Failing test: plain "Copy" (`F6`, no exit) does not exit the app, and every other exit path (menu Cancel, a Confirm/Result screen's own escape/back, `Ctrl+C` cancel) still exits with a falsy (`None`) result — same file, confirms FR-006's scope boundary
- [X] T007 [US1] Failing test: `commands/interactive.py`'s `--tui` path prints `Copied invocation: {invocation}` via `click.echo()` when `InteractiveTUIApp.run()` returns a non-`None` string, and prints nothing when it returns `None` — in `tests/integration/test_interactive.py`, using `monkeypatch` on `sys.stdin.isatty`/`sys.stdout.isatty` (to pass the existing interactive-terminal guard) and on `InteractiveTUIApp.run` (to avoid launching a real Textual app under `CliRunner`, consistent with how Textual screen behavior is tested via `Pilot`/`run_test()` elsewhere in this codebase, not via `CliRunner`)

### Implementation for User Story 1

- [X] T008 [US1] `InteractiveTUIApp(App[None])` → `InteractiveTUIApp(App[str | None])` in `src/ome_zarr_tools/tui/app.py` (depends on T001-T007 existing and failing)
- [X] T009 [P] [US1] `CommandFormScreen.action_copy_and_exit()`: `self.app.exit(result=None)` → `self.app.exit(result=self._invocation_text())` in `src/ome_zarr_tools/tui/app.py` (depends on T008)
- [X] T010 [P] [US1] `InspectScreen.action_copy_and_exit()`: same change in `src/ome_zarr_tools/tui/screens/inspect_screen.py` (depends on T008)
- [X] T011 [P] [US1] `_BaseMetadataScreen.action_copy_and_exit()`: same change in `src/ome_zarr_tools/tui/screens/metadata_screen.py` (depends on T008)
- [X] T012 [P] [US1] `_BaseConfirmScreen.action_copy_and_exit()`: same change in `src/ome_zarr_tools/tui/screens/metadata_screen.py` (depends on T008)
- [X] T013 [P] [US1] `ConfigScreen.action_copy_and_exit()`: same change in `src/ome_zarr_tools/tui/screens/config_screen.py` (depends on T008)
- [X] T014 [US1] `_run_tui()` in `src/ome_zarr_tools/commands/interactive.py`: capture `app.run()`'s return value; `if invocation: click.echo(f"Copied invocation: {invocation}")` (depends on T008-T013)

**Checkpoint**: User Story 1 fully functional — run `pytest tests/integration/test_tui_copy_exit.py tests/integration/test_interactive.py -q` to validate independently.

---

## Phase 2: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and doc-sync — no further behavior changes.

- [X] T015 `ruff check src tests`, `ruff format --check src tests`, `mypy src` all clean
- [X] T016 Full `pytest` suite green (including the pre-existing suite, unaffected by this feature) — run as 6 sequential batches by file (contract/, non-TUI integration, 3× TUI integration groups, unit/), not one combined process, after a full-suite run aborted with a native crash ("Abort (core dumped)") from cumulative resource pressure on this HPC user slice, unrelated to this feature (this exact batching, plus isolated reruns of the files that had errored in the crashed run, is also how the crash was diagnosed as pre-existing rather than caused by this change). All 6 batches passed (180 tests); the one flaky failure hit (`test_run_navigates_immediately_then_shows_failure`, this session's already-documented async-timing pattern) passed cleanly on its own.
- [ ] T017 [P] Run `quickstart.md`'s manual walkthrough in a real terminal (ideally one with broken OSC 52 clipboard passthrough, e.g. tmux without `set-clipboard on`) to confirm the printed fallback is genuinely visible and selectable after exit — the one thing headless `Pilot`/`CliRunner` tests can't fully prove (terminal-restoration timing)
- [X] T018 [P] Update spec 004's `tasks.md`/`data-model.md` cross-references if any — checked, none exist (spec 004 never documented `action_copy_and_exit()`'s clipboard/exit-result mechanism at implementation-detail level, only the shared shortcut's existence)

---

## Dependencies & Execution Order

- All of Phase 1's tests (T001-T007) can be written in parallel — different assertions, same new test file (or, for T007, a different existing file) — but must all be committed/failing before any implementation task starts (constitution Principle II).
- T008 (the `App[str | None]` type change) blocks every per-screen change (T009-T013), since `self.app.exit(result=...)` with a `str` argument is only type-correct once the App's type parameter allows it.
- T009-T013 are independent of each other (5 different files/regions) — fully parallelizable once T008 lands.
- T014 depends on all of T008-T013, since it's the piece that actually reads and prints the value they now produce.
- Phase 2 depends on all of Phase 1.

## Parallel Example: User Story 1

```bash
# Tests (after confirming the new test file doesn't yet exist / fails to import the not-yet-changed behavior):
Task: "Failing test: CommandFormScreen.action_copy_and_exit() exit result"
Task: "Failing test: InspectScreen.action_copy_and_exit() exit result"
Task: "Failing test: fix_metadata/migrate Form screens' action_copy_and_exit() exit result"
Task: "Failing test: fix_metadata/migrate Confirm screens' action_copy_and_exit() exit result"
Task: "Failing test: ConfigScreen.action_copy_and_exit() exit result"

# Implementation (after T008 lands):
Task: "CommandFormScreen.action_copy_and_exit() -> result=self._invocation_text()"
Task: "InspectScreen.action_copy_and_exit() -> result=self._invocation_text()"
Task: "_BaseMetadataScreen.action_copy_and_exit() -> result=self._invocation_text()"
Task: "_BaseConfirmScreen.action_copy_and_exit() -> result=self._invocation_text()"
Task: "ConfigScreen.action_copy_and_exit() -> result=self._invocation_text()"
```

## Implementation Strategy

Single-story MVP: T001-T014 delivers the entire feature (spec has only one
user story). Phase 2 is quality-gate confirmation, not new behavior.
