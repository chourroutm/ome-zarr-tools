# Implementation Plan: Unify label-aware resampling across downsample/upsample/apply_mask

**Branch**: `008-unify-resampling` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-unify-resampling/spec.md`

## Summary

`downsample`, `upsample`, and `apply_mask` each currently resample arrays their own separate way: `downsample`'s label path already used a per-label-channel-argmax primitive, its non-label path used `ngff_zarr.to_multiscales()`, `upsample` softens label boundaries via its own `--smooth <sigma>` float option, `apply_mask` had its own bespoke nearest-neighbor/mean-block-reduce helpers, and `from_images`'s initial pyramid was built entirely by the third-party `bioio_ome_zarr.writers.OMEZarrWriter`. This feature consolidates all of that onto two shared, dependency-light primitives in a new `core/resample.py` (`intensity_downsample`, `label_downsample`), both parameterized by a `downsample_func` defaulting to `skimage.transform.pyramid_gaussian`, both lazy end-to-end via `dask.array.map_blocks` (no array is ever fully materialized). `downsample` gains a `--label` flag; `upsample`'s existing `--smooth <sigma>` is renamed to the same `--label` boolean flag (fixed internal sigma, no longer CLI-tunable) so both commands share one name/semantics. `apply_mask` is switched to the shared primitives. `bioio-ome-zarr` is removed entirely (`from_images` gets a new from-scratch pyramid writer, `core/pyramid.py::write_new_pyramid`, built on the same shared primitive); `ngff_zarr` is removed from `downsample` and remains only in `migrate`.

> **Correction during implementation**: earlier drafts of this plan assumed `upsample --label` already existed and was out of scope. It doesn't — the actual repository baseline still has `upsample --smooth <sigma>` (a prior, unrelated exploratory rename to `--label` was reverted before this feature's `/speckit-specify` run, and the revert wasn't accounted for when this plan was first written). Renaming `upsample`'s flag is genuinely part of this feature's scope (User Story 2), not a pre-existing given.

## Technical Context

**Language/Version**: Python >=3.10 (developed/tested against 3.12)

**Primary Dependencies**: `click` (CLI), `zarr>=3.0` (storage), `dask[array]` (lazy/chunked array ops), `scikit-image>=0.23` (`skimage.transform.pyramid_gaussian`, the default `downsample_func`), `numpy`, `ome-zarr-models` (metadata validation); `ngff-zarr` remains a dependency but scoped to `migrate` only; `bioio-ome-zarr` is removed entirely.

**Storage**: OME-Zarr datasets (Zarr v2/v3) on local or remote (`gs://`, `s3://`) stores.

**Testing**: `pytest` (`tests/unit`, `tests/integration`, `tests/contract`), `ruff check`, `mypy` — per constitution Quality Gates, all three must pass with zero issues before the change is done.

**Target Platform**: Linux CLI/TUI tool (also runs in this HPC environment on organ-scale microscopy/CT volumes).

**Project Type**: Single-project CLI/TUI tool (`src/ome_zarr_tools/{commands,core,io,tui}`, `tests/{unit,integration,contract}`).

**Performance Goals**: N/A (no throughput target); the relevant goal is *memory-boundedness* (see Constraints), not speed.

**Constraints**: Downsampling MUST NOT require an entire array (or an entire pyramid level) to be resident in memory at once — every resample primitive operates per-`dask`-chunk via `map_blocks`. Multi-level pyramid writes MUST batch their `da.store()` calls (one combined call across all levels of a single command invocation) rather than one call per level, since separate calls would force dask to redundantly recompute shared upstream work once per level (verified empirically during design: 3 separate `da.store()` calls reread/reprocess the same upstream source 3 times; one batched call reads it once).

**Scale/Scope**: Three existing commands (`downsample`, `upsample`, `apply_mask`) plus one (`from_images`) whose pyramid-writing internals are replaced; one new module (`core/resample.py`); one new function in the existing `core/pyramid.py`; one dependency removed (`bioio-ome-zarr`); one dependency's usage narrowed (`ngff_zarr`, to `migrate` only). No new CLI surface beyond `downsample --label` (mirroring `upsample`'s existing flag) and no test-fixture-visible changes beyond the two files (`from_images.py`, `tests/conftest.py`) that previously depended on `bioio_ome_zarr`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Code Quality & Best Practice**: Satisfied by design — this feature actively *removes* an unused-elsewhere dependency (`bioio-ome-zarr`) and *collapses* three separate resampling implementations into two shared functions (less duplication, not more). No speculative config/flags are introduced. `ruff`/`mypy` must be zero-issue before done (Quality Gate, re-verified in Phase 1's re-check below).
- **II. Test-First Development (NON-NEGOTIABLE)**: Every behavioral change here (new `downsample --label` flag, `apply_mask`'s internal resampling swap, `from_images`'s writer swap) needs a failing-then-passing automated test. `tests/conftest.py`'s `_write_ome_zarr()` fixture helper is shared by ~19 other test files — the full suite (not just this feature's own new tests) is the regression gate for that change, per the constitution's "full suite MUST pass" requirement.
- **III. Deliberate Commit Discipline**: Out of scope for planning itself; applies at commit time (new commits only, never amending prior history — already the working convention in this repo).
- **No violations requiring Complexity Tracking.**

**Post-Phase-1 re-check**: Design artifacts (`research.md`, `data-model.md`, `contracts/`, `quickstart.md`) introduce one new module (`core/resample.py`) and one new function (`core/pyramid.py::write_new_pyramid`) — both directly reused by existing callers rather than adding parallel/competing abstractions, and both replace code being deleted (`apply_mask`'s bespoke helpers, `bioio_ome_zarr`'s writer) rather than adding net-new surface. `commit_new_levels`'s internal batching change is verified (empirically, during design) to preserve its existing external contract and safety guarantees exactly. No new violations; still no Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/008-unify-resampling/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/ome_zarr_tools/
├── commands/
│   ├── downsample.py     # unify _build_new_coarser_levels + _build_label_coarser_levels
│   │                      # into one _build_coarser_levels(..., label: bool); drop ngff_zarr import
│   ├── upsample.py        # rename its existing --smooth <sigma> option to --label (a
│   │                      # boolean flag, matching downsample's), using a fixed internal
│   │                      # sigma for _smooth_labels when set (no longer user-tunable via
│   │                      # CLI) -- corrects an earlier planning assumption that this was
│   │                      # already done; it wasn't (see plan.md's own note below)
│   ├── apply_mask.py      # swap its own upsample_mask/downsample_mask for the shared
│   │                      # core.resample primitives
│   ├── from_images.py     # swap bioio_ome_zarr.writers.OMEZarrWriter for
│   │                      # core.pyramid.write_new_pyramid; drop _level_shapes()
│   └── migrate.py         # UNCHANGED — keeps its own ngff_zarr usage exactly as-is
├── core/
│   ├── resample.py        # NEW — intensity_downsample, label_downsample (both
│   │                      # dask.Array -> dask.Array, lazy via map_blocks,
│   │                      # downsample_func param defaulting to
│   │                      # skimage.transform.pyramid_gaussian)
│   └── pyramid.py         # add write_new_pyramid (+ _pyramid_compressor helper);
│                          # batch commit_new_levels's per-level da.store() calls
└── ...                    # unchanged

tests/
├── conftest.py            # _write_ome_zarr() fixture helper switches to write_new_pyramid
├── unit/                  # new/updated coverage for core/resample.py, core/pyramid.py
├── integration/           # downsample --label, apply_mask (mask resampling), from_images
└── contract/               # CLI surface tests (--help output, option defaults)
```

**Structure Decision**: Single existing project, no new top-level directories. All changes land inside the existing `src/ome_zarr_tools/{commands,core}` and `tests/{unit,integration,contract}` trees, following the codebase's existing module boundaries (`core/` for shared logic reused by multiple `commands/`, exactly the role `core/pyramid.py` already plays for `downsample`/`upsample`).

## Complexity Tracking

*No constitution violations — table intentionally omitted.*
