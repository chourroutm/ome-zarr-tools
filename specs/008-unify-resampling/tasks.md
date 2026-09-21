---

description: "Task list for: Unify label-aware resampling across downsample/upsample/apply_mask"

---

# Tasks: Unify label-aware resampling across downsample/upsample/apply_mask

**Input**: Design documents from `/specs/008-unify-resampling/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included and REQUIRED — this project's constitution (Principle II, NON-NEGOTIABLE) mandates an automated test for every behavioral change; write each story's tests first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) so each can be implemented, tested, and delivered independently in order.

> Revised after `/speckit-analyze`: fixed D1 (missing `ruff format --check` in T001/T025), D2 (missing TUI coverage — added T010), E1 (missing memory-boundedness test — added T019), E2 (missing single-distinct-value edge case — folded into T005), F1 (T017's import-absence assertion narrowed out, left solely to T018), C1 (T018's file path pinned explicitly), B1 (T028's "reasonable" made concrete). Task IDs renumbered accordingly.
>
> **Revised again mid-implementation**: discovered `upsample --label` was incorrectly assumed pre-existing/out-of-scope (a prior, unrelated exploratory rename to `--label` had been reverted before this feature was specified, and that revert wasn't accounted for). Corrected spec.md/plan.md/data-model.md/contracts/research.md and added real US2 tasks (T013–T015) for the rename. Task IDs renumbered accordingly (28 tasks total).

## Path Conventions

Single project: `src/ome_zarr_tools/`, `tests/{unit,integration,contract}/` at repository root (per plan.md's Project Structure).

## Phase 1: Setup

**Purpose**: Confirm a clean starting baseline before any change (no new project scaffolding needed — this is an existing, mature codebase).

- [X] T001 Confirm `ruff check src/ome_zarr_tools tests`, `ruff format --check src/ome_zarr_tools tests`, `mypy src/ome_zarr_tools`, and `pytest -q` are all green on the current `main` baseline before starting (constitution Quality Gates) — no file changes, just a pre-flight check.

**Checkpoint**: Clean, green baseline confirmed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared resampling primitives and pyramid-writing helpers every later user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Create `src/ome_zarr_tools/core/resample.py` with `intensity_downsample(data: da.Array, factor=2, *, downsample_func=skimage.transform.pyramid_gaussian) -> da.Array` and `label_downsample(data: da.Array, factor=2, *, smooth=None, downsample_func=skimage.transform.pyramid_gaussian) -> da.Array`, both lazy via `dask.array.map_blocks` per `contracts/resample-api.md` (per-block output shape = `math.ceil(block_size / factor)`, verified against `skimage.transform.pyramid_gaussian`'s real convention; `label_downsample`'s per-label-channel decomposition runs block-local, not globally).
- [X] T003 [P] Add `_pyramid_compressor(zarr_format) -> Blosc | BloscCodec` and `write_new_pyramid(path, arr, num_downsampling, *, axes_names, axes_types, axes_units, voxel_size, chunk_shape, shard_shape, zarr_format, image_name, downsample_func=skimage.transform.pyramid_gaussian) -> None` to `src/ome_zarr_tools/core/pyramid.py`, per `contracts/resample-api.md` and `data-model.md` — level shape *and* scale metadata both derived from the real lazy output of `intensity_downsample` (never an independently precomputed shape, per `research.md`'s bug writeup); writes only a `"scale"` transform per dataset (no translation, no `"omero"` block); one combined `da.store()` call across every level.
- [X] T004 Change `src/ome_zarr_tools/core/pyramid.py::commit_new_levels` to collect every level's `(source, target)` pair during its existing create-array/collision-retry loop, then issue one combined `da.store(sources, targets)` call after the loop instead of one `da.store()` call per level inside it — preserves existing collision-retry and rollback-on-failure behavior exactly (per `research.md`'s batching decision).
- [X] T005 [P] `tests/unit/test_resample.py` (new): unit tests for `intensity_downsample`/`label_downsample` covering (a) both stay lazy — no `.compute()` triggered by calling them, (b) `label_downsample` never introduces a value absent from the source, including when different labels appear only in different chunks, (c) output shape for an odd-sized dimension (e.g. 17) matches `skimage`'s real ceiling-division convention, not floor, (d) a dataset containing only a single distinct value (e.g. an all-zero mask) downsamples cleanly with that sole value preserved exactly.
- [X] T006 [P] `tests/unit/test_pyramid.py` (extend existing file): unit tests for `write_new_pyramid` covering (a) scale metadata for an odd-sized dimension matches the *actual* written level shape (regression test for the bug in `research.md`), (b) exactly one `da.store()` call is issued for a multi-level pyramid (not one per level — assert via a call-counting/instrumented source, mirroring the empirical check in `research.md`).

**Checkpoint**: Shared primitives exist, are correct in isolation, and are ready for every user story to build on.

---

## Phase 3: User Story 1 - Label-safe resampling everywhere a mask or segmentation dataset is resized (Priority: P1) 🎯 MVP

**Goal**: `downsample --label` and `apply_mask`'s mask resampling both guarantee every output voxel is one already present in the source — using the shared primitives from Phase 2. (`upsample`'s own label-boundary-softening step is a separate, same-shape concern renamed in User Story 2 — see the correction note above; its default exact-repeat upsampling path, `core.resample.nearest_upsample`, is already label-safe regardless and used here as-is.)

**Independent Test**: Run `downsample --label` and `apply_mask` (with a mask whose resolution doesn't match its volume) against label/mask fixtures; assert every output value is a subset of the source's values.

### Tests for User Story 1 ⚠️ (write first, confirm failing before implementation)

- [X] T007 [P] [US1] Integration test in `tests/integration/test_downsample.py`: `downsample --label` on a binary mask dataset never produces a value outside `{0, 1}` in the newly added level.
- [X] T008 [P] [US1] Integration test in `tests/integration/test_apply_mask.py`: `apply_mask` with a mask requiring downsampling (mask resolution finer than the volume's) never introduces a mask value absent from the source mask.
- [X] T009 [P] [US1] Contract test in `tests/contract/test_downsample.py`: `downsample --help` lists a `--label` option.
- [X] T010 [P] [US1] Headless Textual test in `tests/integration/test_tui_downsample_upsample.py`: after selecting `downsample` in the TUI menu, confirm its form renders a `--label` `Checkbox` (id `field-label`), matching the existing pattern already asserted for `upsample`'s own `--label` field once T015 (US2) lands (constitution Quality Gates: TUI-facing changes must be exercised, and this codebase's TUI auto-generates its forms from `click` option definitions, so this new flag is TUI-facing).

### Implementation for User Story 1

- [X] T011 [US1] Add `_build_label_coarser_levels(zarr_path, num_levels, downsample_func=...)` (using `core.resample.label_downsample`) and a `--label` `click.option` flag to `src/ome_zarr_tools/commands/downsample.py`; dispatch to it when `--label` is set. The existing `ngff_zarr`-based non-label path (`_build_new_coarser_levels`) is left as-is for now — it's swapped out in User Story 3.
- [X] T012 [US1] Swap `src/ome_zarr_tools/commands/apply_mask.py`'s own `upsample_mask`/`downsample_mask` helpers for `core.resample.nearest_upsample`/`label_downsample` directly (per `contracts/cli-contract.md`'s `apply_mask` behavior guarantee); remove the now-unused local helper functions.

**Checkpoint**: `downsample --label` and `apply_mask` both guarantee label-safety via the shared, tested primitive, exercised at the CLI surface (TUI check T010 lands fully once T015 also lands, since it compares against `upsample`'s field). This is a fully functional, independently deliverable MVP.

---

## Phase 4: User Story 2 - Consistent `--label` option across downsample and upsample (Priority: P2)

**Goal**: `downsample --help` and `upsample --help` present the same `--label` option name and description intent. `upsample`'s existing `--smooth <sigma>` is renamed to `--label` (boolean, fixed internal sigma) — see `research.md`'s correction note for why this is real, in-scope work rather than already done.

**Independent Test**: Run both `--help` commands and compare; run `upsample --label` and confirm it still softens boundaries while keeping every voxel one of the source's original label values.

### Tests for User Story 2 ⚠️ (write/update first, confirm failing before implementation)

- [X] T013 [P] [US2] Contract test in `tests/contract/test_downsample.py` and `tests/contract/test_upsample.py`: both `--help` outputs contain a `--label` option; assert the option name matches exactly between the two. (Will fail against `upsample`'s current `--smooth` until T015 lands.)
- [X] T014 [P] [US2] Update `tests/integration/test_upsample.py`'s and `tests/contract/test_upsample.py`'s existing `--smooth <sigma>`-based tests (e.g. the ones asserting smoothed levels stay within the source's label values, and the one asserting `--help` shows `--smooth`) to invoke `--label` instead (no value) and assert against the renamed option; confirm these updated tests fail against the current `--smooth`-based CLI.

### Implementation for User Story 2

- [X] T015 [US2] In `src/ome_zarr_tools/commands/upsample.py`: rename the `--smooth` `click.option` (`type=float, default=None`) to `--label` (`is_flag=True`); replace `_build_new_finer_levels`'s `smooth: float | None` parameter with a `label: bool` one; when `label` is set, call `_smooth_labels` with a fixed internal sigma constant (`_LABEL_SMOOTH_SIGMA = 1.0`) instead of a caller-supplied value; update the option's help text to match `downsample --label`'s "treat this dataset as discrete label/segmentation data" framing (per `contracts/cli-contract.md`).

**Checkpoint**: Both commands document and implement `--label` consistently — same name, same "boolean, fixed internal behavior" shape; a user familiar with one immediately understands the other. T010 (US1's TUI test) and T009 (US1's `--help` test) are both now fully meaningful against `upsample`'s real current form.

---

## Phase 5: User Story 3 - Building large pyramids without exhausting memory (Priority: P3)

**Goal**: `from_images` no longer depends on `bioio-ome-zarr`; its pyramid (and `downsample`'s non-label path) is built via the lazy, `downsample_func`-parameterized primitives from Phase 2, with metadata always derived from real (not precomputed) shapes, batched `da.store()` writes, and a demonstrated bound on per-step memory use.

**Independent Test**: Build a pyramid via `from_images` (with `--num_downsampling >= 1`) and via `downsample` (non-label, `--num_levels >= 1`) on both even- and odd-dimensioned inputs; confirm correct shapes/scale metadata, that `bioio-ome-zarr` is no longer imported anywhere, and that per-step memory use is bounded independent of total dataset size.

### Tests for User Story 3 ⚠️

- [X] T016 [P] [US3] Integration test in `tests/integration/test_from_images.py`: building a pyramid from a volume with an odd (non-power-of-two) dimension produces a level-1 scale value matching that level's *actual* on-disk shape (regression test for the bug in `research.md`).
- [X] T017 [P] [US3] Integration test in `tests/integration/test_downsample.py`: the default (non-`--label`) path still produces the correct shape chain (existing assertions from prior coverage). (Import-absence — i.e. that `ngff_zarr` is no longer used on this path — is a separate static concern, asserted solely by T018; this test is behavioral/shape-chain only.)
- [X] T018 [P] [US3] New file `tests/unit/test_dependencies.py`: assert (via `importlib`/module-inspection, or a scripted `grep` over `src/`) that no module under `src/ome_zarr_tools` imports `bioio_ome_zarr`, and that `ngff_zarr` is imported only by `src/ome_zarr_tools/commands/migrate.py`.
- [X] T019 [P] [US3] Integration test (e.g. in `tests/integration/test_from_images.py` or `tests/unit/test_pyramid.py`): build a pyramid via `write_new_pyramid` from an array many times larger (by total logical size) than its own chunk size, instrumenting `core.resample.intensity_downsample`'s per-block function to record the shape of every array it's called with; assert every recorded shape equals the declared chunk shape and never the full array's shape — demonstrating memory use per processing step is bounded independent of total dataset size (FR-007, SC-003) without relying on fragile OS-level memory limits (`resource.setrlimit` deliberately avoided: platform-inconsistent and risks killing the test process outright rather than failing cleanly).

### Implementation for User Story 3

- [X] T020 [US3] Rewrite `src/ome_zarr_tools/commands/from_images.py`: replace the `bioio_ome_zarr.writers.OMEZarrWriter` construction (and its `try/except ImportError` guard) with a call to `core.pyramid.write_new_pyramid`; remove the now-unused `_level_shapes()` helper. The existing `add_half_pixel_translations`/`write_multiscales` post-step is unchanged.
- [X] T021 [US3] Rewrite `tests/conftest.py`'s `_write_ome_zarr()` fixture helper to call `core.pyramid.write_new_pyramid` instead of `bioio_ome_zarr.writers.OMEZarrWriter`; remove the now-unused import. (This fixture backs ~19 other test files — Phase 6's full-suite run is the regression gate for this change specifically.)
- [X] T022 [US3] In `src/ome_zarr_tools/commands/downsample.py`, unify `_build_new_coarser_levels` (T011's untouched `ngff_zarr`-based non-label path) and `_build_label_coarser_levels` (from T011) into one `_build_coarser_levels(zarr_path, num_levels, *, label: bool, downsample_func=...)`, swapping the non-label path from `ngff_zarr.to_multiscales()` to `core.resample.intensity_downsample`; remove the `ngff_zarr` import entirely.
- [X] T023 [US3] Remove the `"bioio-ome-zarr>=1.1"` line from `pyproject.toml`'s `[project.dependencies]`.

**Checkpoint**: `bioio-ome-zarr` is fully removed; `ngff_zarr` remains only in `migrate.py`; every pyramid-building operation outside `migrate` is lazy, dependency-light, and demonstrably bounded in per-step memory use.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all three stories together.

- [X] T024 [P] Run `ruff check src/ome_zarr_tools tests`, `ruff format --check src/ome_zarr_tools tests`, and `mypy src/ome_zarr_tools`; fix any issues across all files touched in Phases 2–5.
- [X] T025 Run the full suite (`pytest -q`) as the final regression gate, given `tests/conftest.py`'s wide blast radius (T021) — background with a generous timeout per this environment's conventions; re-verify any Textual-TUI test failure individually before treating it as a real regression (known flaky-under-load pattern in this environment, not specific to this feature).
- [X] T026 [P] Run `quickstart.md`'s manual validation steps 2, 6 (dependency-boundary grep, and the attrs-JSON-dump spot-check for `zarr_format` 2 and 3, including the odd-shape case) directly in a Python shell to visually confirm output matches the documented expectations.
- [X] T027 After T025/T026 pass, and **before any commit**, exercise the changed commands against real (non-synthetic) data in this environment rather than only the tiny synthetic test fixtures — at minimum: convert a real image stack or volume via `from_images` (check for real odd/non-power-of-two dimensions, which the synthetic fixtures never exercise), extend its pyramid via `downsample` both with and without `--label`, and run `apply_mask` with a real mask needing resampling. Confirm outputs open correctly, look visually/statistically sane (e.g. label values still discrete, intensity levels still recognizable), and that resident memory during the run tracks roughly the chunk size and dataset-independent overhead being processed at a time — not the full dataset size (a memory profiler or simple periodic `ru_maxrss`/`ps` sampling during the run is sufficient; a rough order-of-magnitude check, not a precise bound). Ask the user which real dataset(s) to use if none is obvious from context.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (T002/T003 are the primitives every story calls; T004's batching fix is needed as soon as any story feeds a lazy multi-level builder into `commit_new_levels`, which starts in US1).
- **User Story 1 (Phase 3)**: Depends on Phase 2 only. Independently deliverable MVP (T010's TUI assertion is written against `upsample`'s eventual `--label` field and only fully resolves once T015 lands, but T007/T008/T009/T011/T012 are all independently complete and shippable without US2/US3).
- **User Story 2 (Phase 4)**: Depends on Phase 2 only — genuinely independent of US1 (renaming `upsample`'s own flag doesn't touch `downsample.py`/`apply_mask.py`).
- **User Story 3 (Phase 5)**: Depends on Phase 2 and on T011 (US1) having created `_build_label_coarser_levels`, since T022 unifies it with the non-label path in the same file.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Parallel Opportunities

- T002, T003, T005, T006 (Phase 2) can run in parallel (different files; T005/T006 depend on T002/T003 existing but are independent of each other).
- T007, T008, T009, T010 (US1 tests) can run in parallel.
- T013, T014 (US2 tests) can run in parallel.
- T016, T017, T018, T019 (US3 tests) can run in parallel.
- T024 and T026 (Phase 6) can run in parallel.
- **User Story 1 and User Story 2 can be worked on fully in parallel** (Phase 3 and Phase 4 touch disjoint files: `downsample.py`/`apply_mask.py` vs. `upsample.py`) — only User Story 3 has a real ordering dependency on US1.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch in parallel — different files, no dependencies between them:
Task: "Create core/resample.py with intensity_downsample, label_downsample"
Task: "Add write_new_pyramid + _pyramid_compressor to core/pyramid.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocks everything).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: `downsample --label` and `apply_mask` are both label-safe via the shared primitive — this alone is a shippable, valuable increment (`upsample`'s rename, and `bioio-ome-zarr`/`ngff_zarr` cleanup, can land later without blocking it).

### Incremental Delivery

1. Setup + Foundational → shared primitives ready and unit-tested.
2. User Story 1 → label-safety guarantee across `downsample`/`apply_mask` (MVP).
3. User Story 2 → `upsample`'s flag renamed to match, CLI consistency across all three commands.
4. User Story 3 → dependency removal + demonstrated memory-boundedness (the largest blast-radius change, via `tests/conftest.py`).
5. Polish → full-suite regression gate on synthetic test data, then real-data validation, then commit.

---

## Notes

- Tests are required per this project's constitution — write each story's tests first, confirm they fail, then implement.
- T011 (US1) intentionally leaves `downsample`'s non-label path on `ngff_zarr` untouched; T022 (US3) is what removes it, so US1 and US3 stay independently deliverable in priority order even though both eventually touch the same file (`downsample.py`).
- **Required order before any commit**: synthetic test suite (T025) → real-data validation (T027) → commit. Passing the synthetic suite alone is not sufficient to consider the feature done, per the user's explicit instruction — the synthetic fixtures are all small, even-dimensioned arrays and would not surface issues real (larger, possibly odd-dimensioned) data could.
- Commit after each task or logical group, per this project's Deliberate Commit Discipline (new commits only, never amending prior history) — only when the user explicitly asks for a commit.
