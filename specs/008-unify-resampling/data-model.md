# Phase 1 Data Model

This feature has no persistent database/storage model beyond the existing OME-Zarr on-disk representation this codebase already reads/writes. The "entities" here are the data shapes that flow between the new/changed functions.

## Label/segmentation dataset

A Zarr array whose values are discrete category identifiers (e.g. `0`/`1` for a binary mask, `0..N` for a multi-class segmentation).

- **Identity guarantee**: the *set* of values present must never grow after resampling — every output voxel is one of the values already present in the corresponding source region.
- **Produced/consumed by**: `downsample --label`, `upsample --label` (renamed from `--smooth <sigma>` by this feature — see `research.md`), `apply_mask`'s mask input (always treated as this, per spec.md Assumptions).
- **Represented in code as**: a `dask.array.Array` with any integer (or otherwise discrete-comparable) dtype; `core.resample.label_downsample` is the only function that resamples it downward.

## Intensity dataset

A Zarr array of continuous measurement values (e.g. raw microscopy/CT intensities).

- **Identity guarantee**: none beyond standard antialiased-downsampling correctness — blending across a downsampling window is expected and desirable.
- **Produced/consumed by**: `downsample`'s default (non-`--label`) path, `from_images`'s initial pyramid construction (all levels beyond 0).
- **Represented in code as**: a `dask.array.Array` with any numeric dtype; `core.resample.intensity_downsample` is the function that resamples it downward.

## Pyramid level

One resolution tier of a multiscale OME-Zarr dataset.

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | The Zarr array's key under the group (e.g. `"0"`, `"1"`). Arbitrary per the OME-NGFF spec — carries no ordering meaning of its own (existing `next_new_paths` convention, unaffected). |
| `array` | `dask.array.Array` | The level's pixel data. For a level built by this feature's primitives, always lazy until the owning function's own combined `da.store()` call. |
| `shape` | `tuple[int, ...]` | Always derived from `array`'s own (possibly lazily-declared) shape — never from an independently precomputed value (this feature's core correctness fix; see `research.md`). |
| `scale` | `list[float]` | Physical size per voxel per axis, one `coordinateTransformations` entry of `{"type": "scale", "scale": [...]}`. Computed as `voxel_size[i] * (level_0_shape[i] / this_level_shape[i])`, using the *real* `this_level_shape`. |
| `chunks` | `tuple[int, ...]` | On-disk chunk shape; the same nominal size is reused across every level of a given pyramid (matches the previous `bioio_ome_zarr` writer's own behavior — zarr tolerates a chunk size larger than a shrunken level's own shape). |
| `dimension_names` | `list[str] \| None` | Set only for Zarr v3 (OME-NGFF 0.5+) arrays; `None` for Zarr v2 (0.4), which has no such concept. |

**Existing representation reused, unchanged**: `core.pyramid.NewLevel` (dataclass: `path`, `array`, `chunks`, `scale` — no `dimension_names` field, since `commit_new_levels` derives that once for the whole batch from the target dataset's own existing metadata). This feature's `write_new_pyramid` builds the equivalent fields inline (no existing dataset to read `dimension_names` from — it's derived directly from the `zarr_format` parameter instead).

## Validation rules carried over from existing code (unaffected, referenced for context)

- `path` uniqueness against both recorded `datasets` entries and any stray on-disk array (`next_new_paths`, existing, unaffected).
- Post-write OME-NGFF metadata validation via `ome_zarr_models.open_ome_zarr` (`io.ome_metadata.validate`, existing, unaffected) — `commit_new_levels` already runs this after committing; `write_new_pyramid` produces a fresh dataset whose validity is exercised by `from_images`'s own existing tests and this feature's new ones (quickstart.md).
