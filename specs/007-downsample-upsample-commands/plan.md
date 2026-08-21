# Implementation Plan: Downsample and Upsample commands

**Branch**: `007-downsample-upsample-commands` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-downsample-upsample-commands/spec.md`

## Summary

Two new CLI/TUI commands. `downsample` appends N new, coarser multiscale
levels below a dataset's existing coarsest level, built via `ngff_zarr`'s
own `to_multiscales()` (which already exists precisely for this — coarsening
an input image by a given set of scale factors). `upsample` has no library
support for building finer levels at all (verified: `ngff_zarr` only ever
coarsens), so its new, finer levels are hand-built via exact 2x
nearest-neighbor expansion (`dask.array.repeat` per axis — exact, never
interpolates, so label values stay valid by construction) and, when
`--smooth` is given, per-label-channel Gaussian smoothing followed by an
argmax re-snap back to the nearest original discrete label (never leaving
non-discrete values). Both commands only ever *add* new arrays and extend
the existing `multiscales.datasets` list — no existing level's on-disk data
is ever rewritten, so both are cheaper and more targeted than `migrate`'s
whole-dataset temp-then-swap rewrite. In-place mode still needs the same
backup/validate/restore-on-failure safety `migrate` established; `--output`
mode copies the dataset directory first, then extends the copy, so the
original is provably untouched throughout.

## Technical Context

**Language/Version**: Python 3.10+ (existing project baseline)

**Primary Dependencies**: `ngff_zarr` (`to_multiscales()`, verified working
with its default `ITKWASM_GAUSSIAN` method in this environment), `dask[array]`
(already a dependency; `.repeat()` for exact nearest-neighbor upsampling),
`scipy` (new explicit dependency — currently only a transitive dependency via
`scikit-image`; `scipy.ndimage.gaussian_filter` needed for `upsample --smooth`)

**Storage**: Local Zarr stores (directories) — same `ZarrPathParamType` as every other command

**Testing**: pytest + `click.testing.CliRunner` (CLI) + Textual `App.run_test()`/`Pilot` (TUI), matching every existing command

**Target Platform**: Same as the rest of the CLI/TUI — this HPC environment plus any terminal Textual supports

**Project Type**: Single project (existing `src/ome_zarr_tools` CLI/TUI package)

**Performance Goals**: N/A — no explicit performance target; both commands avoid rewriting existing levels specifically to keep cost proportional to the *new* data only, not the whole dataset

**Constraints**: In-place mode must leave the original dataset byte-for-byte
unchanged on any failure (spec FR-005/SC-003); `--output` must leave the
original untouched unconditionally (spec FR-004/SC-002); `upsample`'s smoothing
must never leave non-discrete label values (spec FR-010)

**Scale/Scope**: Two new command modules (`downsample.py`, `upsample.py`),
one new shared helper module for the logic both share (add-levels/backup/
output-copy plumbing), two new TUI prep screens (reusing the generic
`CommandFormScreen` — neither needs a specialized screen; see research.md),
new tests in `tests/{contract,integration}/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Code Quality & Best Practice**: Shared add-levels/safety logic between
  `downsample`/`upsample` is factored into one module (`core/pyramid.py`) so
  the two commands don't duplicate the backup/output-copy/validate plumbing —
  same pattern as `migrate.py`'s own internal `_convert_and_validate()`
  helper. `scipy` is added as an explicit dependency since it's now directly
  imported, not left as an undeclared transitive one. PASS.
- **II. Test-First Development**: Failing tests written before each behavior,
  covering both commands' CLI and TUI paths plus the reordering/backup/output
  edge cases from spec.md's Edge Cases section. PASS (planned, see tasks.md).
- **III. Deliberate Commit Discipline**: No commit without explicit request;
  tree passes lint/type/test at every commit. PASS (process constraint).

No violations. Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/007-downsample-upsample-commands/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/ome_zarr_tools/
├── commands/
│   ├── downsample.py           # new: CLI command
│   ├── upsample.py             # new: CLI command
│   └── migrate.py              # unchanged; validate_output_path() reused (moved to core/, see research.md)
├── core/
│   └── pyramid.py              # new: shared add-levels/backup/output-copy logic
└── tui/
    └── app.py                  # updated: downsample/upsample registered like every other generic-form command

tests/
├── contract/
│   ├── test_downsample.py      # new
│   └── test_upsample.py        # new
└── integration/
    ├── test_downsample.py      # new
    └── test_upsample.py        # new
```

**Structure Decision**: Existing single-project layout is unchanged. Both
commands use the existing generic `CommandFormScreen`/`GenericResultScreen`
TUI path (see research.md) — no new specialized TUI screen files are needed,
matching `extract`/`apply_mask`'s existing precedent of commands with no
specialized screen.

## Complexity Tracking

*No constitution violations — section not applicable.*
