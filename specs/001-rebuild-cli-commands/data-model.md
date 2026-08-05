# Phase 1 Data Model: Rebuild OME-Zarr Tools CLI Package

Entities from `spec.md` § Key Entities, expressed as the fields/relationships/validation each command relies on. None of these are persisted in a database — they are the shapes read from and written to Zarr stores and JSON files on disk.

## OME-Zarr Dataset

Represents a Zarr store (local or `cloudpathlib`-resolvable remote) holding one multiscale image.

| Field | Type | Notes |
|---|---|---|
| `path` | path/URI | Root of the Zarr group. |
| `metadata_version` | string (`"0.4"`, `"0.5"`, …) | Read from `attrs["ome"]["version"]` (or top-level `attrs["multiscales"]` for pre-`"ome"`-namespace stores). Drives `migrate`'s version check. |
| `storage_format` | enum (`"v2"`, `"v3"`) | Detected from the Zarr store's own format markers (e.g. presence of `zarr.json` vs `.zarray`/`.zgroup`). Not independently settable — the OME-NGFF specification fixes `storage_format` for a given `metadata_version` (0.4 → v2, 0.5+ → v3), so `migrate` only ever reports this, never targets it directly. |
| `axes` | list of `{name, type, unit}` | From `multiscales[0].axes`; must have exactly 3 spatial axes for `apply_mask`/`extract` to reason about corner/size/center in (i, j, k). |
| `datasets` | list of `{path, coordinateTransformations}` | One entry per resolution level; `path` is the array key (`"0"`, `"1"`, …) used by `extract`'s `--level`. |
| `levels` | list of dask arrays | Lazily opened via `zarr`/`dask.array.from_zarr`, one per `datasets[i].path`. |

**Validation rules**:
- `metadata_version` and `axes`/`datasets` MUST validate against `ome-zarr-models` before any command treats a write as successful (FR-005, FR-012).
- `extract`/`apply_mask` require at least one resolution level to exist; `migrate`/`fix_metadata` operate even on a dataset with no valid metadata yet (that's the case they're fixing).

## Configuration File

A flat JSON key/value document at user or project scope.

| Field | Type | Notes |
|---|---|---|
| `scope` | enum (`"user"`, `"project"`) | Determines path: `$HOME/.local/ome-zarr-tools.config` or `<project>/ome-zarr-tools.config`. |
| `entries` | `dict[str, str \| int \| float \| bool \| null]` | Arbitrary key/value pairs set via `config set`; typed by `_parse_kv_pair`'s coercion rules (bool/null/int/float/string, in that order). |

**Validation rules**: `set`/`reset` require exactly one of `--user`/`--project`; `--set` values are type-coerced but never schema-validated (config is a free-form default store, not a strict contract).

## Metadata Backup

A point-in-time snapshot of a dataset's prior root attributes, written before `fix_metadata`, `apply_mask`, or `migrate` overwrite anything.

| Field | Type | Notes |
|---|---|---|
| `source_dataset` | path | The dataset the backup was taken from. |
| `timestamp` | ISO-8601-ish string (`YYYYMMDDTHHMMSSZ`) | Used in the backup filename for uniqueness/ordering. |
| `attrs_snapshot` | JSON object | Full copy of `group.attrs` at backup time. |
| `location` | path | `<dataset_name>_zattrs_backup_<timestamp>.json`, written alongside the dataset (per spec Assumptions). |

**Relationship**: One Metadata Backup per write attempt (not per dataset) — a dataset that's `fix_metadata`'d and later `migrate`'d accumulates two backups, each independently restorable.

**Validation rules**: Backup MUST be written and confirmed on disk before the in-place write begins; on post-write validation failure, the command restores `group.attrs` from this exact snapshot (FR-005).

## Command Session (interactive mode)

Ephemeral, in-memory only — not persisted, but modeled here because `interactive`'s behavior depends on its state machine.

| Field | Type | Notes |
|---|---|---|
| `selected_command` | one of the six other subcommand names | Chosen from `interactive`'s top-level menu. |
| `collected_options` | `dict[str, Any]` | Filled in step by step by that command's wizard, using the same option definitions the direct CLI uses (single source of truth — the wizard must not duplicate option metadata). |
| `equivalent_invocation` | string | The direct `ome-zarr-tools <command> [OPTIONS]` line equivalent to what's about to run; shown to the user before execution and on cancel. |
| `state` | enum (`"selecting"`, `"prompting"`, `"confirmed"`, `"cancelled"`, `"executed"`) | Governs FR-011 (cancel before execution leaves no side effects). |

**Validation rules**: Transition to `"executed"` is only reachable from `"confirmed"`; `"cancelled"` is reachable from `"selecting"` or `"prompting"` and always short-circuits before any write.

## Migration Record

Ephemeral result of one `migrate` invocation; printed to the user and used to decide whether a write happens at all.

| Field | Type | Notes |
|---|---|---|
| `dataset` | path | Target of the migration. |
| `source_version` | string | The dataset's detected OME-NGFF specification version. |
| `target_version` | string | The requested target OME-NGFF specification version (default: the tool's current target, e.g. `0.4`). Implies both the metadata schema and the Zarr storage format — see OME-Zarr Dataset's `metadata_version`/`storage_format` coupling below; there is no independent storage-format input. |
| `outcome` | enum (`"migrated"`, `"already_current"`, `"failed"`) | Drives exit code and message (FR-012, User Story 3 Acceptance Scenario 3/4). |
| `backup` | Metadata Backup reference | Present whenever `outcome == "migrated"`. |

**Validation rules**: `outcome = "already_current"` is only set when `source_version == target_version`; otherwise `outcome` is `"migrated"` (on success) or `"failed"` (on error), never a partial/silent state.

## Inspection Report

Ephemeral, read-only result of one `inspect` invocation.

| Field | Type | Notes |
|---|---|---|
| `dataset` | path | Target of the inspection. |
| `levels` | list of per-level records | One per resolution level (see below). |
| `total_stored_bytes` | int | Sum of `levels[*].stored_bytes`. |
| `total_logical_bytes` | int | Sum of `levels[*].logical_bytes`. |
| `metadata_valid` | bool | Whether the dataset's OME metadata currently validates (via the same check `fix_metadata`/`migrate` use); reported, never blocks the rest of the report (User Story 4 Acceptance Scenario 3). |

Each entry in `levels`:

| Field | Type | Notes |
|---|---|---|
| `path` | string | Array key (`"0"`, `"1"`, …), matching OME-Zarr Dataset's `datasets[i].path`. |
| `shape` | tuple of int | Array shape. |
| `dtype` | string | Array dtype. |
| `chunk_shape` | tuple of int | Logical chunk shape. |
| `shard_shape` | tuple of int \| `None` | `None` when the level isn't sharded (Zarr v2 stores, and unsharded Zarr v3 arrays). |
| `stored_bytes` | int | On-disk size, from `zarr`'s own store/array size accounting (see `research.md` § `inspect`). |
| `logical_bytes` | int | `prod(shape) * dtype.itemsize` — uncompressed size. |

**Validation rules**: `stored_bytes` and `logical_bytes` are always reported per level even if `metadata_valid` is `False` — storage facts and metadata validity are independent (FR-017 vs. FR-018 don't gate each other).
