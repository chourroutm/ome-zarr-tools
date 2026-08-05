---

description: "Task list for Textual-Based TUI for Interactive Mode (post-/speckit-clarify redesign)"
---

# Tasks: Textual-Based TUI for Interactive Mode

**Input**: Design documents from `/specs/002-textual-tui-interactive/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/tui-contract.md](./contracts/tui-contract.md), [quickstart.md](./quickstart.md)

**Context**: This supersedes the feature's first `tasks.md` (all 15 tasks completed, matching a Button-and-confirmation-dialog design). `/speckit-clarify` then substantially redesigned the TUI (no button, footer shortcuts, live status/log, diff views, rich panels) — see spec.md's `## Clarifications`. This task list modifies the already-working `--tui` code from that first pass rather than starting from an empty package; task descriptions say "modify"/"extend" where code already exists.

**Tests**: Included — FR-012 requires automated coverage of the menu, field editing, autocomplete, footer shortcuts, status indicator, log, diff view, inspect panels, and config editor.

**Organization**: Tasks are grouped by user story (spec.md priorities: US1–US4 = P1, US5–US7 = P2). Real (not soft) dependencies: US3 depends on US2 (autocomplete extends US2's fields); US4/US6/US7 depend on US2 (need the Form-screen framework, though each opens its own specialized screen); US5 depends on US2's execution runner (Foundational) and extends it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: US1 = prompt flow unchanged, US2 = footer-shortcut navigation, US3 = autocomplete, US4 = fix_metadata/migrate diff, US5 = status/log, US6 = inspect panels, US7 = config editor
- File paths are relative to the repo root and match `plan.md`'s Project Structure.

---

## Phase 1: Setup

- [X] T001 Confirm no new dependencies are needed (`textual`/`textual-autocomplete` already present per `research.md`); run `pytest tests/ -q` once as a pre-redesign baseline (documents the "before" state this feature modifies — all tests from the first `--tui` pass should still be green here)

**Checkpoint**: Baseline suite green before any redesign work starts.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The minimal command-execution mechanism every later story needs. **Must complete before US2, US4, US5, US6, or US7.**

- [X] T002 Implement a minimal worker-thread runner in `src/ome_zarr_tools/tui/execution.py`: `run_command(app, command, tokens)` that calls `command.main(args=tokens, standalone_mode=False)` inside `app.run_worker(..., thread=True)` and reports completion/failure back to the UI thread via `app.call_from_thread(...)` (no progress/log capture yet — that's US5, T020). This is what lets Run (US2) execute without freezing the UI or needing the app to exit first (research.md's worker-thread decision).

**Checkpoint**: A command can be launched via `run_command` from a headless `App.run_test()` session and its completion observed without blocking `pilot.pause()`.

---

## Phase 3: User Story 1 - Keep Using the Existing Prompt-Based Flow (Priority: P1)

**Goal**: Confirm FR-001's non-regression guarantee still holds after this feature's Phase 4+ rewiring of `interactive.py`/`tui/app.py`.

**Independent Test**: Run `interactive` (no flag) and confirm menu, wizards, cancellation, and confirmation wording are still byte-for-byte what they were before this redesign.

- [X] T003 [US1] Re-run `tests/integration/test_interactive.py::test_interactive_prompt_flow_unchanged_regression` (already exists, from the first `--tui` pass) after each later phase in this feature; the prompt-based code path itself is not touched by this redesign, so no code change is expected here — if this test ever needs updating, that is itself a signal something leaked into the prompt-based path and must be fixed, not the assertion weakened.

**Checkpoint**: `pytest tests/contract/test_interactive.py tests/integration/test_interactive.py -q` passes, unchanged.

---

## Phase 4: User Story 2 - Navigate a Full-Screen Terminal UI With Keyboard Shortcuts, Not Buttons (Priority: P1)

**Goal**: Replace the first pass's Button-and-`app.exit(result=...)` design with footer-displayed Run/Copy/Copy-and-exit shortcuts, a live equivalent-invocation display, and in-place execution (via T002's runner) with no confirmation dialog (FR-005).

**Independent Test**: Launch `--tui` headlessly, fill a simple command's fields, confirm the invocation text is visible before any shortcut is pressed, then exercise Run (executes immediately, no dialog), Copy (copies + logs, doesn't run), and Copy-and-exit (same + closes) independently.

### Tests for User Story 2

- [X] T004 [P] [US2] Update/extend `tests/contract/test_interactive_tui.py`: assert the Command Form screen has **no** `Button` widget; assert Run/Copy/Copy-and-exit/log-toggle are all present as key bindings shown in the footer (per `contracts/tui-contract.md` § Footer shortcuts); **re-run the existing `test_tui_without_interactive_terminal_fails_clearly` unchanged** against T008's simplified `_run_tui` and confirm it still passes (FR-010/SC-004 regression guard — T008 touches the same function this test exercises)
- [X] T005 [P] [US2] Update/extend `tests/integration/test_interactive_tui.py`: headless session pressing Run on a simple command (e.g. `config`) and asserting it executes (via T002's runner) with no confirmation prompt appearing, given the invocation text was already visible; separate assertions for Copy (clipboard write attempted, log gains a line, nothing executes — mock/spy `App.copy_to_clipboard`) and Copy-and-exit (same, plus the app exits); **re-run the existing `test_select_edit_revisit_and_submit_matches_prompt_tokens`** against T006's rebuilt `CommandFormScreen` and fix it if the new live-invocation-text/binding changes affect field navigation (SC-003 regression guard — T006 rewrites the exact screen this test targets)

### Implementation for User Story 2

- [X] T006 [US2] Modify `src/ome_zarr_tools/tui/app.py`'s `CommandFormScreen`: remove the `Button`/`on_button_pressed`/`_submit` machinery; add `BINDINGS` for run/copy/copy-and-exit/toggle-log actions (`contracts/tui-contract.md` § Footer shortcuts); add a reactive `Static`/`Label` showing the live equivalent invocation, recomputed on every field change via `widget_value_to_tokens` (data-model.md § TUI Session); `action_run` invokes T002's `run_command` instead of `self.app.exit(result=...)` — the screen/app no longer exits automatically when Run is pressed (research.md: stays open for live status)
- [X] T007 [US2] Implement Copy/Copy-and-exit actions on `CommandFormScreen`: `action_copy` calls `self.app.copy_to_clipboard(invocation)` **and** unconditionally appends the invocation as a line to the (not-yet-built, stubbed for now) log buffer (research.md: no failure signal from OSC 52, so always do both); `action_copy_and_exit` does the same then calls `self.app.exit()`
- [X] T008 [US2] Simplify `src/ome_zarr_tools/commands/interactive.py`'s `_run_tui`: the TUI no longer hands back `(command, tokens)` for a post-exit `_confirm_and_run` call (execution now happens inside the app via T006); update it to just run the app and let a normal exit (Escape/Ctrl+C/Copy-and-exit) return control to the shell with no further action — `_confirm_and_run` remains used only by the prompt-based path (`_run_wizard`, US1, unchanged). **Preserve the existing `sys.stdin.isatty()`/`sys.stdout.isatty()` guard unchanged** (FR-010/SC-004) — this simplification touches only the post-app-exit hand-off, not the pre-app-start terminal check; see T004's re-run of the no-tty test for the check that verifies this.

**Checkpoint**: `pytest tests/contract/test_interactive_tui.py tests/integration/test_interactive_tui.py -q` passes for menu/form/Run/Copy/Copy-and-exit/cancel. `quickstart.md` § 3 runs clean manually.

---

## Phase 5: User Story 3 - Get Path Suggestions While Typing (Priority: P1)

**Goal**: Confirm `SafePathAutoComplete` (built in the first `--tui` pass, unchanged by this redesign's `fields.py`) still attaches and works correctly against the rebuilt `CommandFormScreen` (Phase 4).

**Independent Test**: Focus a path field in the redesigned TUI, type a partial real path, confirm suggestions still appear and behave exactly as before (including the `PermissionError`-tolerance fix).

- [X] T009 [US3] Re-run the existing autocomplete tests (`tests/contract/test_interactive_tui.py::test_path_field_gets_autocomplete_non_path_field_does_not`, `tests/integration/test_interactive_tui.py`'s autocomplete tests) against the Phase 4 screen rewrite; `tui/fields.py` itself is unchanged by this redesign, so no new implementation is expected — fix any breakage surfaced by T006's screen changes here, not by touching `fields.py`'s autocomplete logic.

**Checkpoint**: `pytest tests/contract/test_interactive_tui.py tests/integration/test_interactive_tui.py -q` passes in full, including autocomplete. `quickstart.md` § 4 runs clean manually.

---

## Phase 6: User Story 4 - Review a Diff Before fix_metadata or migrate Writes Anything (Priority: P1)

**Goal**: `fix_metadata` and `migrate`'s Command Form is replaced by a specialized screen that always shows a Diff View and a rich view/edit surface before Run can act (FR-018/FR-019) — computed without restructuring either command's real, tested write path (research.md).

**Independent Test**: Open `fix_metadata`/`migrate`'s screen for both a dataset with existing metadata and one with none; confirm the diff/rich view appears immediately, updates as the form/target-version changes, flags invalid edits, and that Run (once pressed) produces a result matching the diff shown.

### Tests for User Story 4

- [X] T010 [P] [US4] In `tests/integration/test_tui_diff.py` (new): unit tests for the pure functions extracted in T013/T014 — assert `build_proposed_multiscales(...)` and `preview_migration(...)` produce output identical to today's inline logic; re-run `001-rebuild-cli-commands`'s existing `tests/contract/test_fix_metadata.py`, `tests/integration/test_fix_metadata.py`, `tests/contract/test_migrate.py`, `tests/integration/test_migrate.py` unchanged (regression guard for the extraction)
- [X] T011 [P] [US4] In `tests/integration/test_tui_diff.py`: headless test opening `fix_metadata`'s screen for a dataset with existing metadata (diff shows real before/after) and one with none (empty "before", per spec.md User Story 4 Acceptance Scenario 3); edit the rich view to an invalid value (e.g. non-numeric voxel size) and assert it's flagged inline and Run is blocked; fix it and assert Run then executes and the resulting dataset matches what the diff showed
- [X] T012 [P] [US4] In `tests/integration/test_tui_diff.py`: headless test opening `migrate`'s screen; assert the rich view is a read-only preview that changes when `--target_version` changes, computed with zero filesystem writes until Run is pressed (assert the real dataset is untouched before Run)

### Implementation for User Story 4

- [X] T013 [US4] In `src/ome_zarr_tools/commands/fix_metadata.py`, extract the existing inline "build proposed multiscales from name/unit/voxel_size/axis_names/dataset_paths" logic into a standalone `build_proposed_multiscales(...) -> list[dict]` function; update the command body to call it — no CLI behavior change (verified by T010)
- [X] T014 [US4] In `src/ome_zarr_tools/commands/migrate.py`, add `preview_migration(path, target_version) -> dict` calling the same `ngff_zarr.from_ngff_zarr()`/`to_ngff_zarr()` pair the real command uses, but targeting an in-memory `zarr.storage.MemoryStore()` (research.md, verified: zero filesystem I/O, nothing to clean up); reuse the existing `detect_version` call for the "before" side — no CLI behavior change (verified by T010)
- [X] T015 [US4] Implement `src/ome_zarr_tools/tui/diff.py`: `render_diff(before: dict, after: dict) -> RichLog content` via `difflib.unified_diff` over `json.dumps(..., indent=2)`, with `+`/`-` lines colored using Rich `Text` styling (research.md)
- [X] T016 [US4] Implement `src/ome_zarr_tools/tui/screens/metadata_screen.py`: for `fix_metadata`, a screen combining T015's Diff View with an editable `TextArea(language="json")` rich view (edits recompute the diff live, invalid edits show `validation_error` inline per data-model.md's Rich View/Edit Surface, blocking the Run action); for `migrate`, the same Diff View with a read-only `TextArea` preview from T014, recomputed whenever `--target_version` changes; both wire their Run/Copy/Copy-and-exit footer actions the same way T006/T007 did for the generic form
- [X] T017 [US4] Modify `src/ome_zarr_tools/tui/app.py`'s command-selection dispatch: selecting `fix_metadata` or `migrate` from the Command Menu opens `metadata_screen.py`'s specialized screen instead of the generic `CommandFormScreen`; every other command is unaffected

**Checkpoint**: `pytest tests/integration/test_tui_diff.py -q` passes; `001-rebuild-cli-commands`'s `fix_metadata`/`migrate` test suites still pass unchanged. `quickstart.md` § 5 runs clean manually.

---

## Phase 7: User Story 5 - See Live Status While a Command Runs (Priority: P2)

**Goal**: Extend T002's runner with real progress (via a generic `dask.callbacks.Callback`) and a captured log (via `stdout` redirection), and surface both through `ProgressBar`/`Sparkline` and a toggleable `RichLog` (research.md).

**Independent Test**: Run a dask-backed command (e.g. `apply_mask`) from the TUI and watch the status indicator become a `ProgressBar` advancing to completion; run a non-dask command (e.g. `config`) and confirm it shows the indeterminate `Sparkline` instead; toggle the log during and after a run without interrupting it.

### Tests for User Story 5

- [X] T018 [P] [US5] In `tests/integration/test_tui_execution.py` (new): run a small dask-backed command (e.g. `apply_mask` against the project's existing small fixtures) through the runner and assert the status indicator transitions from indeterminate to quantified with `done` reaching `total`; run `config` and assert it stays indeterminate (`Sparkline`) for its whole (brief) execution
- [X] T019 [P] [US5] In `tests/integration/test_tui_execution.py`: assert the log-toggle shortcut shows/hides the `RichLog` without pausing or clearing an in-progress or just-completed run's captured lines; assert captured lines match what the equivalent direct CLI invocation would print via `click.echo`

### Implementation for User Story 5

- [X] T020 [US5] Extend `src/ome_zarr_tools/tui/execution.py`'s `run_command`: register a `dask.callbacks.Callback` (context-manager scoped to the `command.main(...)` call) with `start_state` (capture `len(dsk)` as total) and `posttask` (increment done), pushing updates via `call_from_thread`; redirect `sys.stdout` during the same call to a stream whose `.write()` forwards chunks via `call_from_thread` to a log buffer (research.md)
- [X] T021 [US5] Implement `src/ome_zarr_tools/tui/status.py`: a status widget wrapping Textual's `ProgressBar`/`Sparkline` (indeterminate `Sparkline` fed a `set_interval`-updated synthetic rolling buffer by default; switches to `ProgressBar` on the first quantified update from T020 and never reverts — data-model.md § Status Indicator) plus a `RichLog`-backed `Command Log` widget, hidden by default, toggled via the log-toggle binding from T006
- [X] T022 [US5] Mount `tui/status.py`'s widgets into both `CommandFormScreen` (T006) and `metadata_screen.py` (T016), driven by T020's callbacks, so every command (including `fix_metadata`/`migrate`) gets live status/log once Run is pressed

**Checkpoint**: `pytest tests/integration/test_tui_execution.py -q` passes. `quickstart.md` § 6 runs clean manually.

---

## Phase 8: User Story 6 - Browse a Dataset's Structure Through Rich Inspect Panels (Priority: P2)

**Goal**: `inspect`'s screen presents a scrollable, syntax-highlighted JSON-per-level panel and a structure-summary panel, switchable, reusing `inspect`'s existing report-building logic (FR-016).

**Independent Test**: Run `inspect` against a known dataset from the TUI and confirm the JSON panel's per-level content matches `inspect --format json`'s output and the summary panel's figures match the default text output.

- [X] T023 [P] [US6] In `tests/integration/test_tui_screens.py` (new): headless test running `inspect` against a fixture dataset from the TUI; assert the JSON panel's content for each level matches `ome_zarr_tools.commands.inspect.build_report`'s output for the same dataset, and the summary panel's figures (shapes, sizes, chunk/shard layout) match too; assert a keyboard shortcut switches between the two panels
- [X] T024 [US6] Implement `src/ome_zarr_tools/tui/screens/inspect_screen.py`: build one `TextArea(language="json", read_only=True)` per resolution level and a summary panel, both sourced from `commands/inspect.py`'s existing `build_report` (reused, not reimplemented — data-model.md § Inspect Panels), switchable via a keyboard shortcut (spec.md Assumptions: tabbed, not simultaneous)
- [X] T025 [US6] Modify `tui/app.py`'s command-selection dispatch: selecting `inspect` opens `inspect_screen.py` instead of the generic `CommandFormScreen`, once `ZARR_PATH` is provided

**Checkpoint**: `pytest tests/integration/test_tui_screens.py -k inspect -q` passes. `quickstart.md` § 7 runs clean manually.

---

## Phase 9: User Story 7 - Edit Configuration in a Rich JSON Editor (Priority: P2)

**Goal**: `config`'s screen lets the user pick user/project scope, see current values vs. built-in defaults, and edit the underlying JSON file directly, validated the same way `config set` already validates (FR-017).

**Independent Test**: Open the config screen, switch scopes, confirm current/defaults match what `config show`/the CLI's documented defaults report, edit the JSON (including an invalid edit), and confirm saving matches what `config set` would have produced (or is correctly blocked).

- [X] T026 [P] [US7] In `tests/integration/test_tui_screens.py`: headless test on the config screen — switch between user/project scope and assert shown current values match `config show`'s output for a fixture project config and defaults match the CLI's documented option defaults; edit the JSON editor to valid content and assert saving reproduces what `config set` would write; edit to invalid JSON and assert save is blocked with the edit preserved
- [X] T027 [US7] Implement `src/ome_zarr_tools/tui/screens/config_screen.py`: a scope picker (user/project), a read-only current-vs-defaults view (reusing `commands/config.py`'s existing `_read_config` and the CLI's documented defaults), and a `TextArea(language="json")` editor whose save path validates JSON syntax and `config set`'s existing semantic validation before writing (data-model.md § Config Editor)
- [X] T028 [US7] Modify `tui/app.py`'s command-selection dispatch: selecting `config` opens `config_screen.py` instead of the generic `CommandFormScreen`

**Checkpoint**: `pytest tests/integration/test_tui_screens.py -k config -q` passes. `quickstart.md` § 8 runs clean manually.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T029 [P] Update `README.md`'s `interactive --tui` description to reflect the redesign (footer shortcuts, no button/confirmation, status/log, per-command rich panels) — replace the button/confirmation-dialog wording from the first pass
- [X] T030 [P] Run `ruff check`, `ruff format --check`, and `mypy src/ome_zarr_tools/tui src/ome_zarr_tools/commands/interactive.py src/ome_zarr_tools/commands/fix_metadata.py src/ome_zarr_tools/commands/migrate.py` and fix any findings
- [X] T031 Run all of `quickstart.md` (§ 1–10) end-to-end — automated suite plus the manual real-terminal checks — and confirm SC-001 through SC-008, alongside a full re-run of `001-rebuild-cli-commands`'s existing test suite to confirm zero cross-feature regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — blocks US2, US4, US5, US6, US7.
- **US1 (Phase 3)**: Depends on Foundational only (verifying nothing broke); independent of all other stories.
- **US2 (Phase 4)**: Depends on Foundational (T002's runner).
- **US3 (Phase 5)**: Depends on **US2** (T006's rebuilt Form screen) — real dependency, unchanged from the first pass's finding.
- **US4 (Phase 6)**: Depends on **US2** (needs the Form-screen/footer-shortcut framework T006–T008 built, even though it opens its own specialized screen) and Foundational (T002).
- **US5 (Phase 7)**: Depends on **US2** (T002's runner, extended here) — real dependency; also plugs into US4's `metadata_screen.py` (T022), so US5 should land after US4 or expect a small follow-up wiring step.
- **US6 (Phase 8)**: Depends on **US2** (Form-screen framework, T006–T008) for the dispatch mechanism it hooks into.
- **US7 (Phase 9)**: Depends on **US2** (same as US6).
- **Polish (Phase 10)**: Depends on all seven user stories being complete.

### User Story Dependencies

- US1 is independent of everything else.
- US3, US4, US6, US7 all depend on US2's rebuilt Form-screen/dispatch mechanism, but are otherwise independent of each other.
- US5 depends on US2 directly (extends T002) and, for full coverage of `fix_metadata`/`migrate`'s status/log (T022), on US4's `metadata_screen.py` existing — sequence US4 before US5, or treat T022 as a small follow-up task once both are done.

### Within Each User Story

- Tests before implementation (tests must fail first).
- US2: T006 (screen rewrite) before T007 (copy actions, same screen) before T008 (interactive.py wiring, depends on the screen no longer returning a result to act on).
- US4: T013/T014 (pure-function extractions) before T015 (diff rendering, needs `before`/`after` dicts to render) before T016 (screen, uses T015) before T017 (dispatch wiring, uses T016).
- US5: T020 (runner extension) before T021 (status widget, consumes T020's callbacks) before T022 (mounting into screens from US2/US4).
- US6/US7: implementation before dispatch-wiring task, same pattern as US4.

### Parallel Opportunities

- US2 tests: T004, T005 in parallel.
- US4 tests: T010, T011, T012 in parallel (different concerns, same new test file — coordinate merges).
- US5 tests: T018, T019 in parallel.
- US6/US7 tests: T023, T026 in parallel (different files, independent screens).
- Polish: T029, T030 in parallel; T031 last.
- **Across stories**: once US2 (Phase 4) is done, US3 (Phase 5), US4 (Phase 6), US6 (Phase 8), and US7 (Phase 9) can all proceed in parallel by different contributors; US5 (Phase 7) should follow US4 given T022's dependency.

---

## Parallel Example: User Story 4

```bash
# Launch all three US4 test tasks together:
Task: "Unit tests for build_proposed_multiscales/preview_migration + 001 regression in tests/integration/test_tui_diff.py"
Task: "Integration test: fix_metadata diff/rich-view (existing + no-prior-metadata cases) in tests/integration/test_tui_diff.py"
Task: "Integration test: migrate diff/preview (in-memory, zero writes before Run) in tests/integration/test_tui_diff.py"

# Implementation is sequential (each consumes the previous):
# T013 (fix_metadata extraction) + T014 (migrate preview) -> T015 (diff.py) -> T016 (metadata_screen.py) -> T017 (dispatch wiring)
```

---

## Implementation Strategy

### MVP First (this redesign's minimum shippable slice)

1. Phase 1: Setup
2. Phase 2: Foundational (worker-thread runner)
3. Phase 3: User Story 1 (confirms nothing broke)
4. Phase 4: User Story 2 (footer shortcuts, no button, no confirmation — the core of the redesign)
5. **STOP and VALIDATE**: `pytest`, then `quickstart.md` § 2–3
6. This alone replaces the confirmation-dialog design with the requested footer-shortcut model for every command — a complete, demoable increment even before US4–US7's rich panels land.

### Incremental Delivery

1. Setup + Foundational → runner ready
2. US1 → validate → confirms the redesign hasn't regressed the prompt-based flow
3. US2 → validate → footer shortcuts replace the button everywhere (MVP above)
4. US3 → validate → autocomplete confirmed working against the rebuilt screen
5. US4 → validate → the safety-critical diff view is live for `fix_metadata`/`migrate`
6. US5 → validate → every command gets live status/log
7. US6 → validate → `inspect` gets its rich panels
8. US7 → validate → `config` gets its rich editor
9. Polish → README, lint/type-check, full quickstart + full regression suite

### Parallel Team Strategy

After Phase 4 (US2) lands:
- Contributor A: Phase 6 (US4) — safety-critical, prioritize first among the parallel branches
- Contributor B: Phase 8 (US6)
- Contributor C: Phase 9 (US7)
- Phase 7 (US5) follows once Contributor A's Phase 6 is far enough along for T022's wiring step

**Merge caveat**: T017, T025, and T028 all add a branch to the *same* command-selection dispatch conditional in `tui/app.py` (matching `001-rebuild-cli-commands`'s equivalent caveat for its `cli.py` registration tasks). The rest of each contributor's work (T013–T016, T024, T027) is in separate files and genuinely parallel; only these three dispatch-wiring tasks need sequential merging or explicit coordination, not the whole phase.

---

## Notes

- [P] tasks touch different files (or independent concerns within a shared new test file) and have no unmet dependencies within their phase.
- [Story] labels map every user-story-phase task to US1–US7 for traceability back to `spec.md`.
- Commit after each task or logical group.
- Verify each test fails before writing its implementation.
- Re-run `001-rebuild-cli-commands`'s full test suite after every phase in this feature (not just Polish) — `fix_metadata.py`/`migrate.py` are being modified (safely) by US4, and that project's regression gate is the authoritative check that "safely" held.
- `tui/app.py`'s command-selection dispatch tasks (T017, T025, T028) each add one branch to the same conditional and are not parallel with each other across phases if worked on by the same contributor (same file) — safe to parallelize only if contributors coordinate the merge, same convention as `001-rebuild-cli-commands`'s `cli.py` registration tasks.
