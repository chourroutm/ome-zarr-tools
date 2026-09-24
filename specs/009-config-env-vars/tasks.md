---

description: "Task list for feature 009-config-env-vars"

---

# Tasks: Config Command Uses Env-Var Files

**Input**: Design documents from `/specs/009-config-env-vars/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included and REQUIRED — this project's constitution (Principle II, NON-NEGOTIABLE) mandates a failing-then-passing automated test for every behavioral change; the template's "tests are optional" default does not apply here.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every description

## Path Conventions

Single project (existing `src/ome_zarr_tools/`, `tests/`), per plan.md's Project Structure.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before touching anything

- [X] T001 Confirm `ruff check src tests`, `ruff format --check src tests`, `mypy`, and full `pytest` (unit + contract + integration) all pass on the current tree before any change in this feature — no files modified by this task, it's a verification gate only

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure and prerequisite renames every user story needs — the `ConfigurableVariable` registry cannot be written correctly until the options it names have their final shapes (FR-011/FR-012/FR-013)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Write `tests/unit/test_env_file.py`: round-trip read/write of `KEY=VALUE` lines; blank lines and `#`-comment lines are skipped on read; a malformed line (no `=`) raises `CliError` naming the file and 1-indexed line number; a duplicate key returns the last occurrence's value and a warning; `is_valid_env_key()` accepts `^[A-Za-z_][A-Za-z0-9_]*$` and rejects everything else (per data-model.md "Parsing rules" and research.md §4/§6)
- [X] T003 [P] Implement `src/ome_zarr_tools/core/env_file.py` (`read_env_file`, `write_env_file`, `is_valid_env_key`) to make T002 pass
- [X] T004 [P] Rename `from_images`'s `--num_downsampling` to `--num_levels` in `src/ome_zarr_tools/commands/from_images.py` (FR-011) and update its existing references in `tests/contract/test_from_images.py` / `tests/integration/test_from_images.py` (and README.md's from_images option list) to the new name
- [X] T005 [P] Replace `inspect`'s `--format`/`output_format` `Choice(["text","json"])` option with a boolean `--json` flag (dest name `as_json` — NOT `json`, which would shadow `inspect.py`'s own `import json`) in `src/ome_zarr_tools/commands/inspect.py` (FR-012); update `tests/contract/test_inspect.py` and any other reference to `--format`/`output_format` for this command
- [X] T006 [P] Remove `apply_mask`'s `--temporary_upsample` flag entirely from `src/ome_zarr_tools/commands/apply_mask.py` (FR-013, confirmed dead code — see research.md §1) and add a regression test in `tests/contract/test_apply_mask.py` asserting `--temporary_upsample` is now rejected as an unknown option; update README.md's apply_mask option list
- [X] T007 [P] Write `tests/unit/test_config_registry.py`: `OME_ZARR_TOOLS_TARGET_VERSION` and `OME_ZARR_TOOLS_CHUNKS_PER_SHARD` each resolve to targets on both `from_images` and `migrate`; the three `--num_levels` variables (`from_images`/`downsample`/`upsample`) resolve to exactly one target each and never cross-apply; `unrecognized_keys()` flags an unmatched `OME_ZARR_TOOLS_*`-prefixed key but ignores a non-prefixed key (e.g. `AWS_ACCESS_KEY_ID`); `build_default_map()` returns a dict nested by command name (per data-model.md's `ConfigurableVariable` table)
- [X] T008 Implement `src/ome_zarr_tools/core/config_registry.py` (`ConfigurableVariable`, the 13-entry `CONFIGURABLE_VARIABLES` list per data-model.md, `build_default_map()`, `unrecognized_keys()`) to make T007 pass — depends on T004, T005, T006 (needs the renamed/removed options' final dest names)

**Checkpoint**: `core/env_file.py` and `core/config_registry.py` exist and are fully unit-tested; the three option renames/removal have landed with their own passing regression tests. No user-facing config/`--env-file` behavior exists yet.

---

## Phase 3: User Story 1 - Set defaults once, stop repeating flags (Priority: P1) 🎯 MVP

**Goal**: `ome-zarr-tools config set ENV_FILE KEY=VALUE` writes a variable; `ome-zarr-tools --env-file ENV_FILE <command>` makes that command actually use it as a default, unless the flag is passed explicitly.

**Independent Test**: Set one value via `config set`; run an unrelated command with `--env-file` pointed at that file and without the corresponding flag; confirm the command used the configured value. Then pass the flag explicitly and confirm it wins instead (quickstart.md scenarios 1-3).

### Tests for User Story 1

- [X] T009 [P] [US1] Contract test in `tests/contract/test_config.py` (new): `config set ENV_FILE KEY=VALUE` creates `ENV_FILE` if absent; a second `set` call on an already-present key updates it in place (no duplicate line — assert via a subsequent read that no duplicate-key warning appears); an invalid key (e.g. `1BAD=x`) exits non-zero and writes nothing (file absent or unchanged); `set`-ing a new key into a file whose *existing* content already has an unrecognized `OME_ZARR_TOOLS_*` key reports that pre-existing key as an error-level message (FR-016), and a pre-existing duplicate key reports a warning (FR-015) — in both cases the new pair is still written
- [X] T010 [P] [US1] Integration test in `tests/integration/test_cli_env_file_defaults.py` (new): `ome-zarr-tools --env-file FILE from_images ...` (without `--chunk_size`) uses the file's `OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE` value; the same invocation with an explicit `--chunk_size` uses the explicit value instead; omitting `--env-file` entirely behaves exactly as today (built-in default); an invalid value (e.g. `OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=notanumber`) produces a clear, non-crashing error naming the option (FR-009); an unrecognized `OME_ZARR_TOOLS_*` key in the file prints a non-blocking warning and the command still exits 0 (FR-016); a duplicate key in the file prints a warning and the last occurrence's value is the one actually applied (FR-015)

### Implementation for User Story 1

- [X] T011 [US1] Rewrite `src/ome_zarr_tools/commands/config.py`: delete `read_config`/`write_config`/`target_config_path`/`_parse_kv_pair`/`USER_CONFIG_REL`/`PROJECT_CONFIG_NAME`; implement the `set` subcommand as `config set ENV_FILE KEY=VALUE...` (positional `ENV_FILE`, validates every key via `is_valid_env_key` before writing anything, creates the file if missing, updates an existing key's line in place) using `core/env_file.py`; also read the file's existing content first and report any pre-existing duplicate keys (FR-015) or unrecognized `OME_ZARR_TOOLS_*` keys (FR-016, error-level, via `unrecognized_keys()`) before writing the new pairs — depends on T003, T008
- [X] T012 [US1] Add the top-level `--env-file PATH` option to `cli()` in `src/ome_zarr_tools/cli.py` (`exists=True, dir_okay=False`): on given, call `read_env_file`, print any duplicate-key warnings, call `unrecognized_keys()` and print each as a non-blocking warning (`click.echo(..., err=True)`), then `build_default_map()` and assign the result to `ctx.default_map` — an invalid value surfaces as `click`'s own usage error naming the option when the subcommand actually runs (FR-009, no extra handling needed here beyond letting it propagate) — depends on T003, T008

**Checkpoint**: quickstart.md scenarios 1-3 pass. `config show`/`config reset` do not exist yet (US3) and `interactive`/TUI do not yet see `--env-file` (US2) — both acceptable per this story's own independent-test scope.

---

## Phase 4: User Story 2 - Apply a whole set of settings in one shot (Priority: P1)

**Goal**: A file's several values (including a genuinely shared one) all apply together in a single `--env-file` run; the same mechanism reaches commands launched from `interactive`'s wizard and `interactive --tui`; the TUI's main menu surfaces unrecognized-key warnings.

**Independent Test**: A file with `OME_ZARR_TOOLS_TARGET_VERSION` (shared) and one of the `--num_levels` variables (not shared) set together; run a command via direct CLI, via the plain wizard, and via `--tui`; confirm the shared variable applies wherever relevant while `--num_levels` never leaks across commands (quickstart.md scenarios 4, 5, 9).

### Tests for User Story 2

- [X] T013 [P] [US2] Extend `tests/integration/test_cli_env_file_defaults.py`: a file setting both `OME_ZARR_TOOLS_TARGET_VERSION` and `OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS` together — `from_images` and `migrate` both pick up the shared `target_version`; `upsample` (a different command with its own separately-scoped `--num_levels`) is unaffected by the `downsample`-scoped variable in the same file
- [X] T014 [P] [US2] Integration test in `tests/integration/test_interactive.py`: with a `--env-file`-derived mapping available, `interactive`'s plain wizard's `_confirm_and_run` invokes the target command with that mapping as `default_map`, and a value from the file appears in the command's actual result without being typed at the wizard's prompt (the prompt still shows/accepts an override)
- [X] T015 [P] [US2] Headless Textual test in `tests/integration/test_tui_screens.py` (or new `tests/integration/test_tui_menu.py`): `CommandMenuScreen`, constructed with an unrecognized `OME_ZARR_TOOLS_*` key present, shows a warning row below the `OptionList` naming that key; constructed with none, the row is absent entirely

### Implementation for User Story 2

- [X] T016 [US2] In `src/ome_zarr_tools/commands/interactive.py`: read the parsed mapping via `ctx.parent.default_map` (set by T012's group callback); pass `default_map=mapping.get(command.name, {})` into `_confirm_and_run`'s `command.main(...)` call; pass the mapping and `unrecognized_keys()` result into `InteractiveTUIApp`'s constructor for the `--tui` path — depends on T012
- [X] T017 [US2] Add a `default_map: dict[str, object] | None = None` parameter to `run_command` in `src/ome_zarr_tools/tui/execution.py`, forwarded to `command.main(..., default_map=default_map)` — depends on T016
- [X] T018 [US2] Add the below-menu warning row to `CommandMenuScreen` in `src/ome_zarr_tools/tui/app.py`: hidden/absent when `InteractiveTUIApp` has no unrecognized keys, otherwise a `Label`/`Static` naming each one — depends on T016

**Checkpoint**: quickstart.md scenarios 4, 5, and the menu-warning half of scenario 9 pass. US1+US2 together deliver the full `--env-file` mechanism across every way a command can be run in this tool.

---

## Phase 5: User Story 3 - Inspect and clean up a settings file (Priority: P2)

**Goal**: `config show`/`config reset` are fully implemented (including duplicate/unrecognized-key reporting), and the TUI's `ConfigScreen` is rewritten to match the new file format.

**Independent Test**: Set a few values (including one unrecognized-looking and one unrelated key) in a file; `show` it and confirm correct display + correct, narrowly-scoped flagging; `reset` one key and confirm it's gone; `reset --all` and confirm the file is deleted (quickstart.md scenarios 6-8, and the `ConfigScreen` half of scenario 9).

### Tests for User Story 3

- [X] T019 [P] [US3] Contract test in `tests/contract/test_config.py`: `config show ENV_FILE` on a file containing a recognized key, an `OME_ZARR_TOOLS_*`-prefixed unrecognized key, and an unrelated key (e.g. `AWS_ACCESS_KEY_ID`) — only the second is flagged as an error-level message; a duplicate key in the file produces a warning and the displayed value is the last occurrence's
- [X] T020 [P] [US3] Contract test in `tests/contract/test_config.py`: `config reset ENV_FILE KEY` removes that key (no-op if the key isn't present); `config reset ENV_FILE --all` deletes the file; `config show`/`config reset` on a nonexistent `ENV_FILE` both exit non-zero naming the missing path; `config reset ENV_FILE` with neither keys nor `--all`, and with both, both exit non-zero before removing anything (FR-004)
- [X] T021 [P] [US3] Rewrite `tests/integration/test_config.py`: full round trip `set` → `show` → `reset` (one key) → `show` (confirms removal) → `reset --all` → `show` (confirms the "file doesn't exist" error)
- [X] T022 [P] [US3] Headless Textual test in `tests/integration/test_tui_screens.py`: `ConfigScreen`'s `ENV_FILE` `PathField` accepts a path; a default-entry button click inserts a `KEY=VALUE` line (not JSON) using a `CONFIGURABLE_VARIABLES`-sourced name; Run/Save writes the file and `ConfigResultScreen` shows its plain-text content; typing an unrecognized `OME_ZARR_TOOLS_*` key into the editor blocks Save with an error notification, editor content preserved

### Implementation for User Story 3

- [X] T023 [US3] Implement `show` and `reset` subcommands in `src/ome_zarr_tools/commands/config.py` (positional `ENV_FILE`; `show` prints contents + error-level unrecognized-key report + duplicate warning; `reset` removes named keys or deletes the file with `--all`, rejecting a call with neither or both before removing anything (FR-004); both `show`/`reset` error clearly if `ENV_FILE` doesn't exist) — depends on T011, T008
- [X] T024 [US3] Rewrite `src/ome_zarr_tools/tui/screens/config_screen.py` per `contracts/tui-contract.md`: remove the `--user`/`--project` `Select`, the project-dir `Input`, the JSON `TextArea` and its JSON-aware insertion helpers (`_locate_existing_key`, `_location_from_offset`, `_new_key_insertion`); add a required `ENV_FILE` `PathField` (file-only), a plain-text editor backed by `read_env_file`/`write_env_file`, `build_defaults_entries` sourced from `CONFIGURABLE_VARIABLES` (not the old `collect_default_values()`), an error-level unrecognized-key check blocking Save, and an updated `_invocation_text()` reflecting the positional `ENV_FILE` syntax — depends on T008, T023

**Checkpoint**: All three user stories functional independently and together; every quickstart.md scenario (1-9) passes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final verification across all stories

- [X] T025 [P] Update `README.md`: `config` command's description and option list (positional `ENV_FILE`, no `--user`/`--project`), mention the new top-level `--env-file` option in the CLI overview, confirm the TUI section's `config` description matches the rewritten screen
- [X] T026 Run `ruff check src tests`, `ruff format --check src tests`, `mypy`, and the full `pytest` suite (unit + contract + integration, coverage enabled) — fix any fallout from the full feature before considering it done (constitution Quality Gates)
- [X] T027 Manually run every scenario in `quickstart.md` (1-9) end to end against the real CLI and TUI, confirming each documented "Expected" outcome

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (the registry in T008 needs T004/T005/T006's renames to name correctly).
- **User Story 1 (Phase 3)**: Depends on Foundational (T003, T008). No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational, and on US1's T012 (the top-level `--env-file` option and its `ctx.default_map` must exist before `interactive`/TUI can read `ctx.parent.default_map`).
- **User Story 3 (Phase 5)**: Depends on Foundational, and on US1's T011 (`config.py`'s rewrite — `show`/`reset` extend the same file `set` already restructured). Independent of US2.
- **Polish (Phase 6)**: Depends on all three stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only.
- **US2 (P1)**: Foundational + US1's T012 (needs the top-level option to exist before threading it further).
- **US3 (P2)**: Foundational + US1's T011 (needs `config.py`'s new shape before adding `show`/`reset` to it). Does not depend on US2.

### Parallel Opportunities

- Within Foundational: T002 and T007 (test-writing) can run parallel to each other and to T004/T005/T006 (independent renames in different files). T003 and T008 are each gated on their own tests/renames.
- Within US1: T009 and T010 (different test files) in parallel.
- Within US2: T013, T014, T015 (three different test files) in parallel.
- Within US3: T019, T020, T021, T022 (contract tests share one file so T019/T020 are sequential edits to `tests/contract/test_config.py`, but T021/T022 are separate files and can run parallel to T019/T020 and each other).
- US2 and US3 implementation (T016-T018 vs. T023-T024) touch disjoint files and can proceed in parallel once US1 is complete, if staffed.

---

## Parallel Example: Foundational Phase

```bash
# Launch together (independent files):
Task: "Write tests/unit/test_env_file.py"
Task: "Write tests/unit/test_config_registry.py"
Task: "Rename from_images --num_downsampling to --num_levels in src/ome_zarr_tools/commands/from_images.py + its tests"
Task: "Replace inspect --format/output_format with --json in src/ome_zarr_tools/commands/inspect.py + its tests"
Task: "Remove apply_mask --temporary_upsample in src/ome_zarr_tools/commands/apply_mask.py + regression test"
```

## Parallel Example: User Story 2

```bash
# Launch together (independent test files):
Task: "Extend tests/integration/test_cli_env_file_defaults.py for shared-variable + non-shared num_levels behavior"
Task: "Integration test for interactive wizard default_map threading in tests/integration/test_interactive.py"
Task: "Headless Textual test for CommandMenuScreen warning row in tests/integration/test_tui_screens.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocks everything).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run quickstart.md scenarios 1-3 for real.
5. This alone already fixes the core complaint (`config` values that never did anything) — a legitimate demo/deploy point even before US2/US3 land.

### Incremental Delivery

1. Setup + Foundational → shared infrastructure ready, no user-facing change yet.
2. Add US1 → `config set` + top-level `--env-file` work for direct CLI runs → validate → demo (MVP).
3. Add US2 → the same mechanism reaches `interactive`/TUI runs, shared variables proven, menu warning appears → validate → demo.
4. Add US3 → `config show`/`reset` complete, TUI `ConfigScreen` rewritten → validate → demo.
5. Polish → docs + full gate run + manual quickstart pass.

---

## Notes

- [P] tasks touch different files with no unmet dependency.
- Every implementation task in US1-US3 lists the specific tests (same phase) that must fail before it and pass after, per constitution Principle II.
- FR-013 and FR-014 (the two decisions the spec deferred) were already resolved in plan.md/research.md before this task list was written: `--temporary_upsample` is removed (T006), and `migrate` does NOT gain `--chunk_size` (no task exists for it — confirmed absence is the correct outcome, to be double-checked by `/speckit-analyze`).
- Commit only when the user explicitly asks (constitution Principle III) — these tasks describe implementation work, not commit points.
