---

description: "Task list for Rebuild OME-Zarr Tools CLI Package"
---

# Tasks: Rebuild OME-Zarr Tools CLI Package

**Input**: Design documents from `/specs/001-rebuild-cli-commands/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli-contract.md](./contracts/cli-contract.md), [quickstart.md](./quickstart.md)

**Tests**: Included — FR-008 ("package MUST include automated tests covering the success path and at least one failure path for each command") and SC-006 make tests a hard requirement of this feature, not optional.

**Organization**: Tasks are grouped by user story (spec.md priorities: US1 = P1, US2 = P2, US3 = P2, US4 = P3) so each can be implemented, tested, and delivered independently. US4 (`inspect`) was folded into this spec after `/speckit-tasks` had already run once; it's appended as its own phase rather than renumbering anything above it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: US1 = existing 5 commands, US2 = `interactive`, US3 = `migrate`, US4 = `inspect`
- File paths are relative to the repo root and match `plan.md`'s Project Structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the new package skeleton and packaging/tooling config before any command logic is written.

- [X] T001 Create the new package/test tree — `src/ome_zarr_tools/__init__.py`, `src/ome_zarr_tools/cli.py` (empty click group for now), `src/ome_zarr_tools/commands/__init__.py`, `src/ome_zarr_tools/core/__init__.py`, `src/ome_zarr_tools/io/__init__.py`, `tests/contract/__init__.py`, `tests/integration/__init__.py`, `tests/unit/__init__.py`; remove the superseded root-level `ome_zarr_tools/`, root `cli.py`, and `setup.py` (per `plan.md` Project Structure / Structure Decision)
- [X] T002 Write consolidated `pyproject.toml` (PEP 621): project metadata, pinned runtime dependencies (`click`, `numpy`, `dask[array]`, `zarr>=3`, `imageio`, `natsort`, `cloudpathlib`, `scikit-image`, `ome-zarr-models`, `bioio-ome-zarr`, `ngff-zarr` — per `plan.md` Technical Context), `[project.scripts]` entry point `ome-zarr-tools = "ome_zarr_tools.cli:cli"` (FR-010), and `[project.optional-dependencies].dev` (`pytest`, `pytest-cov`, `ruff`, `mypy`) (FR-009)
- [X] T003 [P] Configure `ruff` (lint + format) and `mypy` in `pyproject.toml`
- [X] T004 [P] Configure `pytest` in `pyproject.toml` (`[tool.pytest.ini_options]`: testpaths, coverage) and create `tests/conftest.py` (empty, fixtures added in Phase 2)

**Checkpoint**: `pip install -e .[dev]` succeeds; `ome-zarr-tools --help` runs (shows an empty command group) — nothing functional yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared helpers every command (or ≥2 stories) needs. **Must complete before any user story phase.**

- [X] T005 Implement `src/ome_zarr_tools/core/errors.py`: a `CliError` exception + a click error-handling convention (catch at the group level, print one-line message to stderr, exit non-zero) satisfying FR-004/FR-006
- [X] T006 [P] Implement `src/ome_zarr_tools/core/backup.py`: a `backup_attrs(zarr_group) -> Path` helper that writes a timestamped JSON snapshot of `group.attrs` next to the dataset, and a `restore_attrs(zarr_group, backup_path)` helper — per data-model.md § Metadata Backup, satisfying FR-005
- [X] T007 [P] Implement `src/ome_zarr_tools/io/ome_metadata.py`: read current OME metadata (`attrs["ome"]` or legacy top-level `attrs["multiscales"]`), detect `metadata_version`, and validate a dataset against `ome-zarr-models` — shared by `fix_metadata` (US1) and `migrate` (US3), per data-model.md § OME-Zarr Dataset
- [X] T008 Implement `src/ome_zarr_tools/cli.py`: the top-level `click.Group` (`cli`), wired to `core/errors.py`'s error handling; no subcommands registered yet (each story phase registers its own)
- [X] T009 [P] Build shared test fixtures in `tests/conftest.py`: a synthetic 2D-slice-stack generator, a small on-disk OME-Zarr dataset fixture (valid 0.4/Zarr-v2), and a mask-dataset fixture — used by contract/integration tests across all three stories

**Checkpoint**: Foundation ready — `core/errors.py`, `core/backup.py`, `io/ome_metadata.py`, `cli.py`, and test fixtures all exist. User story phases can now start.

---

## Phase 3: User Story 1 - Convert and Manage Datasets With a Reliable CLI (Priority: P1) 🎯 MVP

**Goal**: The five existing capabilities (`from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`) work end-to-end on the new architecture, each backed by a success-path and a failure-path test.

**Independent Test**: Run each of the five subcommands against `tests/conftest.py`'s fixtures and confirm outputs/exit codes match `contracts/cli-contract.md`.

### Tests for User Story 1

> Write these first; they must fail until the corresponding implementation task lands.

- [X] T010 [P] [US1] Contract test for `from_images` (required/mutually-exclusive input options, `--voxel_size` arity, exit codes) in `tests/contract/test_from_images.py`
- [X] T011 [P] [US1] Contract test for `extract` (corner/size/center/halfsize combinations, exit codes) in `tests/contract/test_extract.py`
- [X] T012 [P] [US1] Contract test for `fix_metadata` (prompts, confirm/abort, backup-then-write) in `tests/contract/test_fix_metadata.py`
- [X] T013 [P] [US1] Contract test for `apply_mask` (required options, threshold default, exit codes) in `tests/contract/test_apply_mask.py`
- [X] T014 [P] [US1] Contract test for `config show|set|reset` (mutually-exclusive `--user`/`--project`, exit codes) in `tests/contract/test_config.py`
- [X] T015 [P] [US1] Integration test: `from_images` success path (stack → valid OME-Zarr, correct voxel size) and failure path (no/conflicting input options) in `tests/integration/test_from_images.py`
- [X] T016 [P] [US1] Integration test: `extract` success path (crop written to output format) and failure path (half-specified crop) in `tests/integration/test_extract.py`
- [X] T017 [P] [US1] Integration test: `fix_metadata` success path (writes valid metadata + backup) and failure path (validation failure restores backup) in `tests/integration/test_fix_metadata.py`
- [X] T018 [P] [US1] Integration test: `apply_mask` success path (mask applied across scales) and failure path (no shared resolution level) in `tests/integration/test_apply_mask.py`
- [X] T019 [P] [US1] Integration test: `config` round-trip (`set`→`show`→`reset`) success path and failure path (neither/both of `--user`/`--project`) in `tests/integration/test_config.py`

### Implementation for User Story 1

- [X] T020 [P] [US1] Implement `src/ome_zarr_tools/io/images.py`: stack/volume reading (try `dask.array.image.imread`, catch `ImportError` only and fall back to `imageio.v3`; no direct `pims` import — per `research.md`)
- [X] T021 [US1] Implement `src/ome_zarr_tools/commands/from_images.py` per `contracts/cli-contract.md` § `from_images` (uses T020 for reading, `bioio_ome_zarr.OmeZarrWriter` for pyramid writing)
- [X] T022 [US1] Implement `src/ome_zarr_tools/commands/extract.py` per `contracts/cli-contract.md` § `extract`
- [X] T023 [US1] Implement `src/ome_zarr_tools/commands/fix_metadata.py` per `contracts/cli-contract.md` § `fix_metadata` (uses T006 for backup, T007 for metadata read/validate)
- [X] T024 [US1] Implement `src/ome_zarr_tools/commands/apply_mask.py` per `contracts/cli-contract.md` § `apply_mask` (uses T006 for backup)
- [X] T025 [US1] Implement `src/ome_zarr_tools/commands/config.py` per `contracts/cli-contract.md` § `config`
- [X] T026 [US1] Register `from_images`, `extract`, `fix_metadata`, `apply_mask`, `config` on the `cli` group in `src/ome_zarr_tools/cli.py` (depends on T021–T025)

**Checkpoint**: `pytest tests/contract tests/integration -k "from_images or extract or fix_metadata or apply_mask or config"` passes. `quickstart.md` § 2 runs clean. This alone is a shippable MVP.

---

## Phase 4: User Story 2 - Discover Commands Through an Interactive Mode (Priority: P2)

**Goal**: `ome-zarr-tools interactive` presents a menu of every currently-registered subcommand and runs a chosen one via a step-by-step wizard built from that command's own click options (no duplicated option metadata).

**Independent Test**: Launch `interactive`, select each command in the menu, supply prompted values, and confirm the result matches the equivalent direct invocation; confirm cancel leaves no side effects.

### Tests for User Story 2

- [X] T027 [P] [US2] Contract test for `interactive` (menu lists every command currently registered on the `cli` group; no flags beyond `--help`) in `tests/contract/test_interactive.py`
- [X] T028 [P] [US2] Integration test: full `interactive` session selecting `from_images`, answering prompts, confirming, and diffing the result against the direct-CLI equivalent; plus a cancel-mid-session test asserting no file is written (FR-011) in `tests/integration/test_interactive.py`

### Implementation for User Story 2

- [X] T029 [US2] Implement `src/ome_zarr_tools/commands/interactive.py`: build the menu and each wizard by introspecting `cli.commands` (the click group from T008) — so it automatically reflects whatever subcommands are registered, including `migrate` once Phase 5 lands — implementing the Command Session state machine from `data-model.md` (`selecting` → `prompting` → `confirmed`/`cancelled` → `executed`), per FR-002/FR-011/FR-016
- [X] T030 [US2] Register `interactive` on the `cli` group in `src/ome_zarr_tools/cli.py` (depends on T029)

**Checkpoint**: `pytest tests/contract tests/integration -k interactive` passes. `quickstart.md` § 3 runs clean, using only the five US1 commands (migrate not yet present is expected at this checkpoint).

---

## Phase 5: User Story 3 - Migrate an OME-Zarr Dataset Forward (Priority: P2)

**Goal**: `ome-zarr-tools migrate ZARR_PATH [--target_version]` upgrades a dataset's OME-NGFF spec version (and, per the spec, its Zarr storage format) using `ngff-zarr`, with confirmation, backup, and validation.

**Independent Test**: Run `migrate` against a fixture dataset at an older spec version and confirm the result validates at the target version with checksum-identical pixel data; confirm a second run reports "already current" and makes no changes.

### Tests for User Story 3

- [X] T031 [P] [US3] Contract test for `migrate` (`--target_version` default/override, "already current" no-op, unrecognized-layout failure) in `tests/contract/test_migrate.py`
- [X] T032 [P] [US3] Integration test: `migrate` success path (0.4/Zarr-v2 fixture → `--target_version 0.5`, dataset validates via `ome-zarr-models`, backup file present, pixel data checksum-equal to source) and idempotency (immediate re-run reports "already current", no writes) in `tests/integration/test_migrate.py`

### Implementation for User Story 3

- [X] T033 [US3] Extend `src/ome_zarr_tools/io/ome_metadata.py` (T007) with `detect_version(zarr_group) -> str`, reused by `migrate` for its source-version check
- [X] T034 [US3] Implement `src/ome_zarr_tools/commands/migrate.py` per `contracts/cli-contract.md` § `migrate`: detect source version (T033), compare to `--target_version`, report and confirm, back up (T006), convert via `ngff_zarr.from_ngff_zarr()` / `ngff_zarr.to_ngff_zarr(..., version=target)` using the default `zarr-python` backend (never `use_tensorstore=True` — per `research.md`), then validate with `ome-zarr-models`
- [X] T035 [US3] Register `migrate` on the `cli` group in `src/ome_zarr_tools/cli.py` (depends on T034) — `interactive`'s menu (T029) picks it up automatically, no changes needed there

**Checkpoint**: `pytest tests/contract tests/integration -k migrate` passes. `quickstart.md` § 4 runs clean. Re-running `quickstart.md` § 3 now shows all six commands in the `interactive` menu.

---

## Phase 6: User Story 4 - Inspect a Dataset's Structure and Storage (Priority: P3)

**Goal**: `ome-zarr-tools inspect ZARR_PATH [--format text|json]` reports per-level and dataset-wide shape, dtype, chunk shape, shard shape, stored size, and logical size — read-only.

**Independent Test**: Run `inspect` against a fixture dataset with known shapes/chunks (and, where the fixture supports it, sharding) and confirm the reported figures match; confirm the dataset is byte-for-byte unchanged afterward.

### Tests for User Story 4

- [X] T036 [P] [US4] Contract test for `inspect` (`--format text|json`, exit codes, read-only — no writes to the target path) in `tests/contract/test_inspect.py`
- [X] T037 [P] [US4] Integration test: `inspect` success path (per-level shape/dtype/chunk/shard/stored/logical size matches a fixture with known values, dataset-wide totals correct, dataset checksum unchanged before/after) and failure path (nonexistent/non-Zarr path) in `tests/integration/test_inspect.py`

### Implementation for User Story 4

- [X] T038 [US4] Implement `src/ome_zarr_tools/commands/inspect.py` per `contracts/cli-contract.md` § `inspect`: build the Inspection Report (data-model.md) per level via `zarr`'s array/store size accounting (chunk shape, shard shape, stored bytes; logical bytes computed from shape × dtype itemsize — per `research.md` § `inspect`), reusing T007's `io/ome_metadata.py` for the `metadata_valid` flag; render as a table (default) or JSON (`--format json`)
- [X] T039 [US4] Register `inspect` on the `cli` group in `src/ome_zarr_tools/cli.py` (depends on T038) — `interactive`'s menu (T029) picks it up automatically, no changes needed there

**Checkpoint**: `pytest tests/contract tests/integration -k inspect` passes. `quickstart.md` § 5 runs clean. Re-running `quickstart.md` § 3 now shows all seven commands in the `interactive` menu.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and whole-suite validation after all four stories are in.

- [X] T040 [P] Update `README.md` to document all eight commands (`from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`, `interactive`, `migrate`, `inspect`), their options, and an old→new option-name mapping table for anything renamed from the current tool (FR-013, FR-014)
- [X] T041 [P] Run `ruff check`, `ruff format --check`, and `mypy src/` across the codebase and fix any findings
- [X] T042 Run all of `quickstart.md` (§ 1–7) end-to-end against a real install and confirm SC-001 through SC-007 are met

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational only (specifically `cli.py` from T008). Independently testable even before US3 exists — its menu just shows five commands rather than six, which is expected per Phase 4's checkpoint note.
- **User Story 3 (Phase 5)**: Depends on Foundational only (T007's `io/ome_metadata.py`, T006's backup helper, T008's `cli.py`). Independently testable without US1/US2.
- **User Story 4 (Phase 6)**: Depends on Foundational only (T007's `io/ome_metadata.py` for the `metadata_valid` flag, T008's `cli.py`). Independently testable without US1/US2/US3.
- **Polish (Phase 7)**: Depends on all four user stories being complete (T040 documents all eight commands; T042 exercises the whole quickstart, § 1–7).

### User Story Dependencies

- US1, US2, US3, US4 are mutually independent once Foundational is done — none blocks another's implementation or tests.
- The only soft coupling is presentational: US2's `interactive` menu is most useful once US3's `migrate` and US4's `inspect` exist too, but nothing in US2's code changes when either lands (T029's introspection design absorbs both automatically).

### Within Each User Story

- Contract/integration tests before implementation (tests must fail first).
- Shared per-story helpers (e.g., T020 `io/images.py`) before the command that uses them (T021).
- Command implementation before its `cli.py` registration task.

### Parallel Opportunities

- Setup: T003, T004 in parallel (after T001, T002).
- Foundational: T006, T007, T009 in parallel (after T005, T008 respectively where noted).
- US1 tests: T010–T019 all in parallel (10 tasks, different files).
- US1 implementation: T020 alone first, then T021–T025 in parallel (different command files), then T026 last (shared `cli.py`).
- US2 tests: T027, T028 in parallel.
- US3 tests: T031, T032 in parallel.
- US4 tests: T036, T037 in parallel.
- Polish: T040, T041 in parallel; T042 last.
- **Across stories**: once Phase 2 is done, Phase 3, Phase 4, Phase 5, and Phase 6 can all proceed in parallel (e.g., four different contributors), since none depends on another's output.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 contract + integration tests together:
Task: "Contract test for from_images in tests/contract/test_from_images.py"
Task: "Contract test for extract in tests/contract/test_extract.py"
Task: "Contract test for fix_metadata in tests/contract/test_fix_metadata.py"
Task: "Contract test for apply_mask in tests/contract/test_apply_mask.py"
Task: "Contract test for config in tests/contract/test_config.py"
Task: "Integration test for from_images in tests/integration/test_from_images.py"
Task: "Integration test for extract in tests/integration/test_extract.py"
Task: "Integration test for fix_metadata in tests/integration/test_fix_metadata.py"
Task: "Integration test for apply_mask in tests/integration/test_apply_mask.py"
Task: "Integration test for config in tests/integration/test_config.py"

# After T020 (io/images.py), launch all five command implementations together:
Task: "Implement src/ome_zarr_tools/commands/from_images.py"
Task: "Implement src/ome_zarr_tools/commands/extract.py"
Task: "Implement src/ome_zarr_tools/commands/fix_metadata.py"
Task: "Implement src/ome_zarr_tools/commands/apply_mask.py"
Task: "Implement src/ome_zarr_tools/commands/config.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational (blocks everything)
3. Phase 3: User Story 1
4. **STOP and VALIDATE**: `pytest`, then `quickstart.md` § 2
5. This is a shippable MVP — the five commands users already depend on, rebuilt.

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate → MVP release
3. User Story 2 (`interactive`) → validate → release
4. User Story 3 (`migrate`) → validate → release
5. User Story 4 (`inspect`) → validate → release (now `interactive`'s menu is complete, all eight commands present)
6. Polish → final release with updated README and full quickstart passing

### Parallel Team Strategy

With multiple contributors, after Phase 2 (Foundational) is done:
- Contributor A: Phase 3 (User Story 1)
- Contributor B: Phase 4 (User Story 2)
- Contributor C: Phase 5 (User Story 3)
- Contributor D: Phase 6 (User Story 4)

All four integrate independently into `cli.py` (each adds its own `add_command` call); Phase 7 runs once all four land.

---

## Notes

- [P] tasks touch different files and have no unmet dependencies within their phase.
- [Story] labels map every user-story-phase task to US1/US2/US3/US4 for traceability back to `spec.md`.
- Commit after each task or logical group.
- Verify each test fails before writing its implementation.
- `cli.py` registration tasks (T026, T030, T035, T039) are each the last task in their phase and are not parallel with each other across phases if worked on by the same contributor (same file) — safe to parallelize only if contributors coordinate the merge.
