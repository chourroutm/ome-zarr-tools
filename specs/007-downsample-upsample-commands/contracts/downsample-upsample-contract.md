# Contract: `downsample` and `upsample` commands

## CLI surface

| Command | Argument | Options |
|---|---|---|
| `downsample` | `ZARR_PATH` (must exist, must be a directory) | `--num_levels` (int, default `1`); `--output` (path, must not already exist) |
| `upsample` | `ZARR_PATH` (must exist, must be a directory) | `--num_levels` (int, default `1`); `--output` (path, must not already exist); `--smooth` (float, Gaussian sigma; omit for no smoothing) |

Both commands' `ZARR_PATH` uses the same `ZarrPathParamType(exists=True, file_okay=False)` every other command with a required dataset argument already uses.

## Behavior

| Element | Rule |
|---|---|
| Validation order | Both commands validate (in order, before any I/O): the output path doesn't already exist (if given) → the dataset's existing multiscales metadata is present and structurally valid (`io/ome_metadata.py::validate`) → (in-place only, computed but not yet acted on) the dataset is ready to be extended. Any failure here writes nothing. |
| `--num_levels` | Both: an integer ≥ 1. `0` or negative is rejected with a clear error (there is nothing to add). |
| New level scale | `downsample`: each new level is 2x coarser than the previous one (relative to the existing coarsest level). `upsample`: each new level is 2x finer than the previous one (relative to the existing finest level). Neither exposes the factor as an option. |
| New level paths | Freshly chosen, non-colliding path strings (next unused integer beyond every existing `datasets[].path`) — never reusing or renaming an existing level's path. |
| List order | `downsample` appends new entries to the end of `multiscales[0].datasets` (existing entries unchanged, new ones coarsest-last). `upsample` prepends new entries to the front (existing entries' relative order unchanged, new ones finest-first — the new overall-finest level ends up at `datasets[0]`). |
| `upsample` upsampling method | Exact 2x nearest-neighbor per axis (`dask.array.repeat`) — never interpolates, so every voxel's value is always one that already existed in the source level. |
| `upsample --smooth <sigma>` | Per new level: decompose into one boolean channel per distinct label value, Gaussian-smooth each channel independently (`scipy.ndimage.gaussian_filter`, the given `sigma`), then take the per-voxel argmax across channels as the new label value. Every output voxel is always one of the original label values — never a blurred/non-discrete one. Omitted `--smooth` → the plain repeated level is used as-is. |
| `--output` | When given: the whole dataset directory is copied there first (rejecting an already-existing path before copying anything); every subsequent step operates on the copy only. The original dataset is never opened for writing in this mode. |
| In-place (no `--output`) | New level arrays are written into the existing group first (inert until referenced); the dataset's root attrs are backed up (`core/backup.py::backup_attrs`); the extended `datasets` list is written; the result is validated. On any failure, newly written arrays are removed and (if attrs were already updated) restored from the backup — no existing level's data is ever touched, so there is nothing to "swap back." |
| Existing levels | Never rewritten, moved, or renamed by either command, in either mode — both commands only ever add new arrays and extend the metadata list. |

## TUI surface

| Element | Rule |
|---|---|
| Screen | Both use the existing generic `CommandFormScreen` (no specialized screen) — same as `extract`/`apply_mask`. Fields: `ZARR_PATH` (required, directory-only Browse picker), `--num_levels` (optional, pre-filled with the CLI default `1`), `--output` (optional, any-mode Browse picker), and — `upsample` only — `--smooth` (optional). |
| Execution | Run executes immediately (User Story 7's existing immediate-Run behavior) and lands on the existing generic `GenericResultScreen` — no Confirm-before-you-commit step (unlike `fix_metadata`/`migrate`), per this feature's own scope (not requested). |

## Who verifies this contract

- `tests/contract/test_downsample.py`, `tests/contract/test_upsample.py` —
  argument/option surface, defaults, validation-order failures.
- `tests/integration/test_downsample.py`, `tests/integration/test_upsample.py` —
  in-place vs `--output` behavior, level count/scale/ordering, existing-data
  untouched, `upsample`'s discreteness/reordering/smoothing guarantees.
