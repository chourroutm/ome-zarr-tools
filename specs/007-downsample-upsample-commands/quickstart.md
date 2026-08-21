# Quickstart: Downsample and Upsample commands

## Prerequisites

- `uv sync` (or equivalent) so `ome-zarr-tools` and its test dependencies are installed.
- An existing OME-Zarr dataset (any fixture from `tests/conftest.py` works) for `downsample`.
- An existing OME-Zarr label/mask dataset for `upsample`.

## Automated validation

```sh
pytest tests/contract/test_downsample.py tests/contract/test_upsample.py -q
pytest tests/integration/test_downsample.py tests/integration/test_upsample.py -q
ruff check src tests && ruff format --check src tests && mypy src
```

Expected: all pass. See
[contracts/downsample-upsample-contract.md](./contracts/downsample-upsample-contract.md)
for exactly what each row of behavior asserts.

## Manual walkthrough (real terminal)

1. `ome-zarr-tools downsample path/to/data.zarr` — confirm a new, coarser
   level is added in place; `ome-zarr-tools inspect path/to/data.zarr` shows
   one more level than before, half the resolution of the previous coarsest.
2. `ome-zarr-tools downsample path/to/data.zarr --num_levels 2 --output path/to/copy.zarr`
   — confirm `data.zarr` is unchanged and `copy.zarr` has 2 extra coarser
   levels.
3. `ome-zarr-tools upsample path/to/mask.zarr` — confirm a new, finer level
   is added in place, and it's now the first level `inspect` reports.
4. `ome-zarr-tools upsample path/to/mask.zarr --smooth 1.0 --output path/to/mask_smooth.zarr`
   — confirm `mask.zarr` is unchanged, and every voxel in the new level of
   `mask_smooth.zarr` is still one of the original mask's label values (no
   fractional/blurred values).
5. Repeat steps 1 and 3 via the TUI (`ome-zarr-tools interactive --tui`) —
   confirm `downsample`/`upsample` appear in the command menu, their forms
   show the expected fields, and Run executes immediately (no confirm step)
   and lands on a Result screen showing success/failure.
