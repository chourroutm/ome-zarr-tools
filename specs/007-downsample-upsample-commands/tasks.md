---

description: "Task list for Downsample and Upsample commands"
---

# Tasks: Downsample and Upsample commands

**Input**: Design documents from `/specs/007-downsample-upsample-commands/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/downsample-upsample-contract.md, quickstart.md

**Tests**: Included and REQUIRED — this project's constitution, Principle II ("Test-First Development"), is non-negotiable. Every task below that changes behavior is preceded by a failing-test task for the same behavior.

**Organization**: Two user stories (`downsample` P1, `upsample` P2) share one Foundational phase (`core/pyramid.py`'s add-levels/backup/output-copy logic, and relocating `validate_output_path` so `migrate` and both new commands share one definition) — both stories depend on it, neither depends on the other.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files/regions, no dependency on an unfinished task)
- **[Story]**: Which user story this task belongs to

## Phase 1: Foundational (blocking prerequisites for both user stories)

**Purpose**: Shared infrastructure both `downsample` and `upsample` build on — must land before either command's own implementation.

- [X] T001 Add `scipy` to `pyproject.toml`'s explicit dependencies (currently only a transitive dependency via `scikit-image`; `core/pyramid.py` will import `scipy.ndimage` directly)
- [X] T002 [P] Failing test: `core/zarr_path.py::validate_output_path` (relocated from `migrate.py`, identical behavior) raises `CliError` for an already-existing path and is a no-op for `None`/a non-existent path — `tests/unit/test_zarr_path.py`
- [X] T003 Move `validate_output_path` from `commands/migrate.py` to `core/zarr_path.py`; update `migrate.py` to import it from there (pure relocation, no behavior change — existing `migrate` tests must keep passing unmodified) (depends on T002)
- [X] T004 [P] Failing test: `core/pyramid.py::next_new_paths(existing_datasets, n)` returns `n` fresh path strings that don't collide with any existing `datasets[].path` — `tests/unit/test_pyramid.py` (new)
- [X] T005 [P] Failing test: `core/pyramid.py`'s commit helper writes new level arrays into a group, extends `multiscales[0].datasets` (both `append` and `prepend` position), and the result validates — same file
- [X] T006 [P] Failing test: same commit helper, when the post-write validation fails, removes the newly written arrays and restores the original root attrs from backup — dataset left exactly as it was — same file
- [X] T007 [P] Failing test: same commit helper's output-copy path (`shutil.copytree` to a not-yet-existing output path, then operates only on the copy) leaves the original dataset directory byte-for-byte unchanged — same file
- [X] T008 Implement `core/pyramid.py`: `next_new_paths()` and the commit helper (write arrays → backup attrs → extend `datasets` list per `position` → validate → restore-on-failure; output-copy wiring) (depends on T004-T007 existing and failing)

**Checkpoint**: `core/pyramid.py` and the relocated `validate_output_path` pass their own unit tests — both user stories can now build on them independently.

---

## Phase 2: User Story 1 - Extend a pyramid with coarser levels (Priority: P1) 🎯 MVP

**Goal**: `downsample` adds N new, coarser multiscale levels below a dataset's existing coarsest level, in place or to a new output path.

**Independent Test**: Run `downsample` on a dataset with an existing 2-level pyramid, no options, and confirm the result has 3 levels, the new level is half the resolution of the previous coarsest, and existing levels' on-disk data is unchanged.

### Tests for User Story 1 ⚠️ write first, confirm they FAIL

- [X] T009 [P] [US1] Failing test: `downsample` with no options adds exactly 1 new, coarser level, in place — `tests/integration/test_downsample.py` (new)
- [X] T010 [P] [US1] Failing test: `downsample --num_levels 3` adds exactly 3 new, progressively coarser levels — same file
- [X] T011 [P] [US1] Failing test: `downsample --output` leaves the original dataset byte-for-byte unchanged and writes the extended pyramid to the new path — same file
- [X] T012 [P] [US1] Failing test: `downsample` on a dataset with missing/invalid multiscales metadata fails cleanly before writing anything — same file
- [X] T013 [P] [US1] Failing test: `downsample --output` to an already-existing path is rejected before writing anything — same file
- [X] T014 [P] [US1] Failing test: existing levels' on-disk array data is byte-for-byte unchanged after an in-place `downsample` — same file
- [X] T015 [P] [US1] Failing test: `downsample`'s CLI argument/option surface — `ZARR_PATH` required, `--num_levels` defaults to `1`, `--output` defaults to `None` — `tests/contract/test_downsample.py` (new)

### Implementation for User Story 1

- [X] T016 [US1] Implement `commands/downsample.py`: read the existing coarsest level, build `--num_levels` new coarser levels via `ngff_zarr.to_multiscales(image, scale_factors=[2**i for i in range(1, n+1)])`, hand the new `(path, array, coordinateTransformations)` entries to `core/pyramid.py`'s commit helper with `position="append"` (depends on T009-T015 existing and failing)
- [X] T017 [US1] Register `downsample` in `cli.py`'s command group (depends on T016)
- [X] T018 [P] [US1] Register `downsample` in the TUI's command list (`tui/app.py`) — uses the existing generic `CommandFormScreen`/`GenericResultScreen`, no new screen needed (depends on T016)
- [X] T019 [P] [US1] Failing-then-passing TUI test: `downsample` appears in the menu; its form shows `ZARR_PATH`/`--num_levels`/`--output`; Run executes immediately and lands on the generic Result screen — `tests/integration/test_tui_screens.py` (depends on T018)

**Checkpoint**: `downsample` fully functional — `pytest tests/contract/test_downsample.py tests/integration/test_downsample.py -q` passes independently of User Story 2.

---

## Phase 3: User Story 2 - Extend a mask's pyramid with finer levels (Priority: P2)

**Goal**: `upsample` adds N new, finer multiscale levels above a mask dataset's existing finest level, reordering the metadata so the new finest level is `datasets[0]`, with optional discreteness-preserving smoothing.

**Independent Test**: Run `upsample` on a mask dataset with an existing single-level pyramid, no options, and confirm the result has 2 levels, the new level is double the resolution of the previous finest, and it's `datasets[0]`.

### Tests for User Story 2 ⚠️ write first, confirm they FAIL

- [X] T020 [P] [US2] Failing test: `upsample` with no options adds exactly 1 new, finer level, in place, and every new voxel's value already existed in the source level (exact repeat, never interpolated) — `tests/integration/test_upsample.py` (new)
- [X] T021 [P] [US2] Failing test: `upsample --num_levels 2` adds exactly 2 new, progressively finer levels — same file
- [X] T022 [P] [US2] Failing test: `upsample --output` leaves the original dataset byte-for-byte unchanged — same file
- [X] T023 [P] [US2] Failing test: the new finest level is reordered to `datasets[0]`; every existing level's on-disk array data (including the previous finest level) is unchanged — same file
- [X] T024 [P] [US2] Failing test: `upsample --smooth <sigma>` — every voxel in the result is one of the source level's original label values (never a blurred/non-discrete value) — same file
- [X] T025 [P] [US2] Failing test: `upsample` without `--smooth` applies no smoothing (the plain repeated/upsampled level is written as-is) — same file
- [X] T026 [P] [US2] Failing test: `upsample --output` to an already-existing path is rejected before writing anything — same file
- [X] T027 [P] [US2] Failing test: `upsample`'s CLI argument/option surface — `ZARR_PATH` required, `--num_levels` defaults to `1`, `--output` defaults to `None`, `--smooth` defaults to `None` — `tests/contract/test_upsample.py` (new)

### Implementation for User Story 2

- [X] T028 [US2] Implement `commands/upsample.py`: read the existing finest level, build `--num_levels` new finer levels by chaining `dask.array.repeat(arr, 2, axis=i)` per spatial axis, apply per-label-channel Gaussian smoothing + argmax re-snap when `--smooth` is given (data-model.md), hand the new entries to `core/pyramid.py`'s commit helper with `position="prepend"` (depends on T020-T027 existing and failing)
- [X] T029 [US2] Register `upsample` in `cli.py`'s command group (depends on T028)
- [X] T030 [P] [US2] Register `upsample` in the TUI's command list (`tui/app.py`) — generic screen, fields include `--smooth` (depends on T028)
- [X] T031 [P] [US2] Failing-then-passing TUI test: `upsample` appears in the menu; its form shows `ZARR_PATH`/`--num_levels`/`--output`/`--smooth`; Run executes immediately and lands on the generic Result screen — same file as T019 (depends on T030)

**Checkpoint**: `upsample` fully functional — `pytest tests/contract/test_upsample.py tests/integration/test_upsample.py -q` passes independently.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates — no further behavior changes.

- [X] T032 `ruff check src tests`, `ruff format --check src tests`, `mypy src` all clean
- [X] T033 Full `pytest` suite green (including the pre-existing suite, unaffected by this feature) — run as 6 sequential batches by file, per this project's established HPC practice
- [ ] T034 [P] Run `quickstart.md`'s manual walkthrough in a real terminal, covering both commands' CLI (in-place + `--output`, `upsample --smooth`) and TUI (menu entries, form fields, Run → Result)

---

## Dependencies & Execution Order

- Phase 1 (T001-T008) blocks both Phase 2 and Phase 3 — `core/pyramid.py` and the relocated `validate_output_path` are shared prerequisites.
- Within Phase 1: T002/T004-T007 (failing tests) can be written in parallel; T003 depends on T002; T008 depends on T004-T007.
- Phase 2 (`downsample`) and Phase 3 (`upsample`) are independent of each other once Phase 1 lands — either can be implemented (and shipped) first.
- Within each user story: all failing-test tasks are parallelizable (different assertions, same new file); the implementation task depends on all of that story's tests existing and failing; CLI registration depends on the implementation; TUI registration and its test can run in parallel with CLI registration once the implementation itself lands.
- Phase 4 depends on both Phase 2 and Phase 3.

## Parallel Example: Foundational phase

```bash
Task: "Failing test: validate_output_path relocated, same behavior"
Task: "Failing test: next_new_paths returns non-colliding paths"
Task: "Failing test: commit helper writes+extends+validates (append/prepend)"
Task: "Failing test: commit helper restores on validation failure"
Task: "Failing test: commit helper's output-copy leaves original untouched"
```

## Implementation Strategy

MVP = Phase 1 + Phase 2 (`downsample` alone is independently shippable and
useful). Phase 3 (`upsample`) adds the mask-specific command on the same
shared foundation. Phase 4 is quality-gate confirmation, not new behavior.
