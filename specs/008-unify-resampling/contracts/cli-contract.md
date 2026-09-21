# Phase 1 Contract: CLI surface changes

`downsample` gains a new `--label` option and `upsample`'s existing `--smooth <sigma>` is renamed to the same `--label` boolean flag. `apply_mask` and `from_images` keep their existing CLI surfaces unchanged — this feature changes their *internal* resampling implementation, not their options (see `resample-api.md` for the internal contract those three now share).

## `downsample ZARR_PATH` (changed)

| Option | Type | Required | Notes |
|---|---|---|---|
| `--num_levels` | int | no (default `1`) | *(unchanged)* |
| `--output` | path | no | *(unchanged)* — write to a new path instead of in place |
| `--label` | flag | no (default off) | **NEW.** Mirrors `upsample --label` exactly: treat `ZARR_PATH` as discrete label/segmentation data. When set, new coarser levels are built via `core.resample.label_downsample` (per-label-channel-argmax, never blending distinct label values). When unset (default, unchanged from before), new levels are built via `core.resample.intensity_downsample` (Gaussian-pyramid antialiasing) instead of the previous `ngff_zarr`-based path — same observable shape/count/path behavior, per FR-004's non-pixel-exact guarantee already established for this path. |
| `ZARR_PATH` (argument) | path (must exist) | yes | *(unchanged)* |

**Exit conditions**: unchanged (`--num_levels < 1` → error; `--output` pointing at an existing path → error; missing multiscales metadata → error).

## `upsample ZARR_PATH` (changed)

| Option | Type | Required | Notes |
|---|---|---|---|
| `--num_levels` | int | no (default `1`) | *(unchanged)* |
| `--output` | path | no | *(unchanged)* |
| `--label` | flag | no (default off) | **RENAMED from `--smooth <sigma>` (float).** Same underlying mechanism (`_smooth_labels`, this command's own same-shape boundary-softening step — a separate concern from `core.resample`'s pyramid-*building* primitives, since upsampling here is always exact-repeat first via `core.resample.nearest_upsample`, already label-safe by construction regardless of this flag) but now a boolean: presence alone triggers softening, using a fixed internal sigma (`_LABEL_SMOOTH_SIGMA`, no longer user-tunable via CLI) instead of a caller-supplied value. Matches `downsample --label`'s name and "treat as label data" framing exactly. |
| `ZARR_PATH` (argument) | path (must exist) | yes | *(unchanged)* |

Its exact-repeat upsampling path (`core.resample.nearest_upsample`) is unaffected by this feature — already label-safe by construction, used regardless of `--label`.

## `apply_mask` (unchanged CLI; internal resampling swapped)

| Option | Type | Required | Notes |
|---|---|---|---|
| `--volume` | path (must exist) | yes | *(unchanged)* |
| `--mask` | path (must exist) | yes | *(unchanged)* |
| `--threshold` | float | no (default `0.5`) | *(unchanged)* |
| `--output` | path | no | *(unchanged, shipped separately/prior)* |

**Behavior guarantee (new, FR-002/FR-003)**: when the mask's resolution doesn't match the volume's at the matching scale, the mask is now resampled via the same shared `core.resample` primitives `downsample`/`upsample` use — `nearest_upsample` when growing the mask's resolution, `label_downsample` when shrinking it (the mask is always treated as label data — see spec.md Assumptions). Previously used its own separate `upsample_mask`/`downsample_mask` helpers with equivalent but independently-implemented logic (nearest-neighbor repeat / mean-block-reduce).

## `from_images OUTPUT_ZARR` (unchanged CLI; internal pyramid writer swapped)

All existing options (`--stack_dir`/`--stack_pattern`/`--vol_file`, `--voxel_size`/`--resolution`, `--voxel_size_unit`/`--resolution_unit`, `--num_downsampling`, `--chunk_size`, `--target_version`, `--chunks_per_shard`, `OUTPUT_ZARR`) are unchanged.

**Behavior guarantee (new, FR-005)**: no longer requires the `bioio-ome-zarr` package (its "not installed" `CliError` exit condition no longer applies — `scikit-image`, which provides the new default `downsample_func`, is already a hard dependency). Initial pyramid levels beyond level 0 are now built via `core.pyramid.write_new_pyramid` (Gaussian-pyramid antialiasing via `core.resample.intensity_downsample`) instead of `bioio_ome_zarr`'s nearest-neighbor `skimage.transform.resize`. Resulting OME-NGFF metadata shape (axes/datasets/scale/translation, per target version) is unchanged (FR-008, SC-004) — only the pixel values of downsampled levels differ (never asserted exactly by existing tests, which check shapes/scale/translation, not level-1+ pixel content).

## `migrate` (unchanged; explicitly out of scope)

Keeps its own existing `ngff_zarr`-based spec-version conversion exactly as-is (FR-006).
