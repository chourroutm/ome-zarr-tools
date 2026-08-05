# Phase 1 Contract: `ome-zarr-tools` CLI Surface

This is the interface contract the package exposes to users (and to scripts calling it). Every subcommand is reachable two ways: directly (`ome-zarr-tools <command> [OPTIONS]`) and via the `interactive` menu, which MUST use these same option definitions rather than a separate copy (data-model.md § Command Session).

**Cross-cutting conventions (FR-004, FR-006)**:
- Exit code `0` = success. Non-zero = failure, with a one-line, human-readable message on stderr — never a raw Python traceback for an expected failure (bad path, bad option combination, missing optional dependency).
- Any command that writes to an existing dataset backs up its current root attributes first (FR-005) and reports the backup path.

## `from_images OUTPUT_ZARR`

Convert a 2D image stack or a 3D volume file into an OME-Zarr dataset.

| Option | Type | Required | Notes |
|---|---|---|---|
| `--stack_dir` | path (must exist) | one of `--stack_dir`/`--stack_pattern`/`--vol_file` | Directory of same-type slice files. |
| `--stack_pattern` | string | " | Glob pattern expanded by Python. |
| `--vol_file` | path (must exist) | " | Single 3D image file. |
| `--voxel_size` / `--resolution` | float × 1 or 3 (repeat the flag once per value, e.g. `--voxel_size 1.0 --voxel_size 1.0 --voxel_size 2.0`) | yes | Broadcast to 3 axes if a single value given. |
| `--voxel_size_unit` / `--resolution_unit` | string | no (default `micrometer`) | |
| `--num_downsampling` | int | no (default `0`) | Pyramid levels below full res. |
| `--chunk_size` | int | no (default `64`) | Isotropic chunk edge length. |
| `OUTPUT_ZARR` (argument) | path | yes | Destination store; must not already exist as a non-empty store. |

**Exit conditions**: non-zero + message if none/more than one of `--stack_dir`/`--stack_pattern`/`--vol_file` resolves to input, if `bioio-ome-zarr` is unavailable, or if `--voxel_size` isn't length 1 or 3.

## `extract ZARR_PATH`

Extract a full resolution level or a crop from an OME-Zarr pyramid.

| Option | Type | Required | Notes |
|---|---|---|---|
| `--corner` | int × 3 (multiple, 0–2 occurrences) | no | One occurrence + `--size`, or two occurrences (order-independent) define the crop. |
| `--size` | int × 3 | with one `--corner` | |
| `--center` | int × 3 | no | Paired with `--halfsize`. |
| `--halfsize` | int | with `--center` | |
| `--mag` | float | no | Mutually resolved with `--scale` (`mag = 1/scale`). |
| `--level` / `--mip` / `--dataset_path` | int | no (default `0`) | Index into the dataset's `multiscales[0].datasets` list (resolution order), **not** a literal array-key string — writers don't all use `"0"`/`"1"` keys (e.g. `migrate`'s `ngff-zarr`-produced stores use `"scale0/<name>"`; see `research.md`). |
| `--scale` | float | no | See `--mag`. |
| `--output` | path | no | Defaults to `<zarr_stem>_level<level><output_format>`. |
| `--output_format` | string | no (default `.ome.tif`) | `.tif`, `.ome.tif`, `.nii`, `.nii.gz`, `.raw`, etc. |
| `ZARR_PATH` (argument) | path (must exist) | yes | |

**Exit conditions**: non-zero if a crop region is only half-specified (`--corner` without `--size`, or vice versa), or if the requested level key isn't present in the store.

## `fix_metadata ZARR_PATH`

Interactively populate/correct an OME-Zarr dataset's root metadata.

| Option | Type | Required | Notes |
|---|---|---|---|
| `ZARR_PATH` (argument) | path (must exist) | yes | |

No flags — every field (name, spatial unit, voxel size, axis names) is collected via prompts, each defaulting to the currently-stored value when present. Writes only on explicit confirmation (`y`/`N` prompt); backs up existing attrs first and restores them if post-write validation fails.

## `apply_mask`

Apply a binary mask to an OME-Zarr volume, resampled to match each resolution level.

| Option | Type | Required | Notes |
|---|---|---|---|
| `--volume` | path (dir, must exist) | yes | |
| `--mask` | path (dir, must exist) | yes | |
| `--threshold` | float | no (default `0.5`) | Binarization cutoff. |
| `--temporary_upsample` | flag | no | Reserved for compatibility; no effect (mask resampling is always applied automatically as needed). |

**Exit conditions**: non-zero if no resolution level key is shared between volume and mask stores.

## `config <show|set|reset>`

Manage user- or project-scoped configuration.

- `config show [--user] [--project PATH]` — no write; prints user config, project config, and (when neither flag given) the merged view.
- `config set (--user | --project PATH) KEY=VALUE...` — requires exactly one of `--user`/`--project`.
- `config reset (--user | --project PATH) [--all] [KEYS...]` — `--all` removes the whole file; otherwise removes the named keys.

**Exit conditions**: non-zero if both or neither of `--user`/`--project` are given to `set`/`reset`, or if the config file contains invalid JSON.

## `interactive` — NEW

Top-level menu over the other six subcommands.

1. Prints a numbered menu of `from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`, `migrate`, `inspect`.
2. On selection, runs that command's wizard, prompting for each of its options above (required options first, optional ones offering their CLI default).
3. Before executing, shows the equivalent direct-CLI invocation and asks for confirmation.
4. On cancel at any point (Ctrl-C or explicit "no"), exits 0 with no side effects (FR-011).

No flags of its own beyond `--help`.

## `migrate ZARR_PATH` — NEW

Upgrade an OME-Zarr dataset to a target OME-NGFF specification version. Implemented on `ngff-zarr`'s `from_ngff_zarr()`/`to_ngff_zarr(..., version=target)` using its default `zarr-python` write backend (never `use_tensorstore=True` — see `research.md`).

| Option | Type | Required | Notes |
|---|---|---|---|
| `ZARR_PATH` (argument) | path (must exist) | yes | |
| `--target_version` | string | no (default: tool's current target, e.g. `0.4`) | A single OME-NGFF specification version. The Zarr storage format (v2 for `0.4`, v3 for `0.5`+) is implied by this version, per the specification, and is not separately selectable. |

Reports source/target version (and the storage-format change that target implies) before writing, asks for confirmation (unless already current, per FR-012), backs up prior metadata, and validates the result with `ome-zarr-models`.

**Exit conditions**: exit `0` with a "nothing to do" message and no writes when the dataset is already at `--target_version`; non-zero if the dataset's current layout/version isn't recognized.

## `inspect ZARR_PATH` — NEW

Read-only report of an OME-Zarr dataset's per-level and total shape, chunk/shard layout, and on-disk vs. logical size. Never writes, backs up, or otherwise modifies the dataset (FR-018).

| Option | Type | Required | Notes |
|---|---|---|---|
| `ZARR_PATH` (argument) | path (must exist) | yes | |
| `--format` | enum (`text`\|`json`) | no (default `text`) | `text` prints a human-readable table; `json` prints the Inspection Report (see `data-model.md`) as machine-readable JSON. |

Output includes, per level: array key, shape, dtype, chunk shape, shard shape (or `none`), stored size, logical size — plus dataset-wide totals for stored and logical size. If the dataset's OME metadata doesn't currently validate, `inspect` still reports all storage-level facts and separately flags the metadata as invalid (User Story 4 Acceptance Scenario 3) rather than refusing to run.

**Exit conditions**: non-zero if `ZARR_PATH` doesn't exist or isn't a Zarr store; always `0` on a dataset that opens successfully, regardless of metadata validity (invalid metadata is reported, not a failure of `inspect` itself).
