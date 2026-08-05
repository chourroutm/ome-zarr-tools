# Implementation Plan: Rebuild OME-Zarr Tools CLI Package

**Branch**: `001-rebuild-cli-commands` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-rebuild-cli-commands/spec.md`

## Summary

Rebuild `ome-zarr-tools` as a single, best-practice Python CLI package. The five existing capabilities (`from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`) are re-implemented on a consistent architecture with pinned dependencies and test coverage, keeping their argument sets as close as possible to what the closed GitHub issues (#2–#8) originally specified and to today's shipped behavior — deviations from the issues were confirmed with the user (see Research). Three new subcommands are added: `interactive` (a top-level menu that launches each other subcommand's own prompt-driven wizard), `migrate` (upgrades an OME-Zarr dataset to a target OME-NGFF specification version, which — per the spec itself — also determines its Zarr storage format), and `inspect` (reports per-level and dataset-wide shape, dtype, chunk/shard layout, and on-disk vs. logical size — read-only, folded into this same feature after `/speckit-tasks` rather than opened separately). `migrate` is built on the `ngff-zarr` library rather than hand-rolled schema translation, chosen after checking its and `bioio`/`bioio-ome-zarr`'s issue trackers for unresolved bugs (see Research); `from_images`/pyramid writing deliberately does **not** adopt `bioio`'s general reader or `ngff-zarr`'s `to_multiscales()` due to stale, unresolved correctness/performance bugs found in each. `inspect` uses `zarr`'s own array/store size-accounting APIs rather than a hand-rolled filesystem walk. Packaging moves to a single PEP 621 `pyproject.toml` (dropping the duplicate, drifted `setup.py`), the package moves to a `src/` layout with one module per subcommand plus shared `core`/`io` helpers, and `pytest` covers a success and a failure path per command.

## Technical Context

**Language/Version**: Python ≥3.10 (project already targets modern Python; no lower-version users identified)

**Primary Dependencies**: `click` (CLI framework), `numpy`, `dask[array]`, `zarr` (≥3, for native Zarr v2 **and** v3 support), `imageio` (image I/O, covers TIFF/JP2K/etc. via its own plugins — see Research), `natsort`, `cloudpathlib` (local/cloud-agnostic paths), `scikit-image` (mask resampling), `ome-zarr-models` (OME metadata validation, now required rather than optional since `fix_metadata` and `migrate` both depend on it), `bioio-ome-zarr` (OME-Zarr pyramid writer used by `from_images`), `ngff-zarr` (drives `migrate`'s spec-version conversion, using its default `zarr-python` write backend — **not** the `tensorstore` backend, which has an open, unreleased-fix codec bug; see Research). Deliberately **not** adopted: the general `bioio` reader package (stale, unresolved TIFF/PNG performance regression) and `ngff-zarr.to_multiscales()` (stale, unresolved pyramid-level rounding bug) — see Research for the issue-tracker findings behind both calls.

**Storage**: Zarr stores on local filesystem or any `cloudpathlib`-supported remote (dataset storage); JSON files for user/project configuration — no database

**Testing**: `pytest` + `pytest-cov`, using `click.testing.CliRunner` for CLI-level tests and small on-disk Zarr fixtures for integration tests

**Target Platform**: Linux/macOS command line (incl. HPC login/compute nodes), installed via `pip`

**Project Type**: Single project — CLI tool (Option 1 structure)

**Performance Goals**: Process datasets larger than available RAM by keeping array operations lazy (`dask`) until an explicit write/compute step; avoid loading a full pyramid level into memory unless the user's requested crop requires it. `inspect` must not load array *data* into memory at all — it only reads array/store metadata and stored-byte counts.

**Constraints**: No command may leave a dataset in a partially-written, invalid state — every in-place write is preceded by a metadata/data backup (per FR-005); commands must fail fast with a non-zero exit code and a human-readable message rather than a raw traceback (FR-004, FR-006)

**Scale/Scope**: Single-user, single-invocation CLI; datasets from a few MB up to multi-TB pyramids accessed chunk-wise through `dask`/`zarr`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still the unfilled template (all sections are `[PLACEHOLDER]`) — no ratified project principles exist yet. No gates apply; nothing to check against. **Recommendation** (not a blocker): run `/speckit-constitution` at some point to capture the practices this plan already assumes (pytest-covered commands, pinned dependencies, no partial writes) so future features are held to the same bar.

## Project Structure

### Documentation (this feature)

```text
specs/001-rebuild-cli-commands/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── cli-contract.md   # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml           # Single source of packaging truth (setup.py removed)
README.md

src/
└── ome_zarr_tools/
    ├── __init__.py
    ├── cli.py                  # click group; registers all subcommands
    ├── commands/
    │   ├── from_images.py
    │   ├── extract.py
    │   ├── fix_metadata.py
    │   ├── apply_mask.py
    │   ├── config.py
    │   ├── interactive.py      # NEW: menu + per-command wizards
    │   ├── migrate.py          # NEW: metadata-version / storage-format migration
    │   └── inspect.py          # NEW: read-only size/chunk/shard report
    ├── core/
    │   ├── backup.py           # shared metadata/data backup helper (FR-005)
    │   └── errors.py           # shared exit-code / error-message conventions (FR-004, FR-006)
    └── io/
        ├── images.py           # stack/volume reading shared by from_images
        └── ome_metadata.py     # OME metadata read/validate/write shared by fix_metadata + migrate

tests/
├── contract/                   # one file per subcommand's CLI surface (options, exit codes)
├── integration/                # end-to-end runs against small on-disk Zarr fixtures
└── unit/                       # pure-function tests (mask resampling, metadata transforms, config parsing)
```

**Structure Decision**: Single-project CLI (Option 1). The package moves from a flat `ome_zarr_tools/` + root `cli.py` layout to a `src/ome_zarr_tools/` layout with one module per subcommand under `commands/`, and small shared `core`/`io` packages so `fix_metadata` and `migrate` can reuse the same OME-metadata helpers instead of duplicating logic. `tests/` gains the `contract`/`integration`/`unit` split called for by FR-008 (a success path and a failure path per command).

## Complexity Tracking

*No constitution gates are defined (see Constitution Check above), so no violations require justification.*
