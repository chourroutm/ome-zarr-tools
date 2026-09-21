# Feature Specification: Unify label-aware resampling across downsample/upsample/apply_mask

**Feature Branch**: `[008-unify-resampling]`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "Unify ome-zarr-tools' mask/pyramid resampling: (1) `downsample` gains a `--label` flag mirroring `upsample`'s existing label-aware smoothing option, so both commands expose the same `--label` boolean switch for treating a dataset as discrete label/segmentation data instead of continuous intensity data, both implemented via shared functions in a new `core/resample.py` module. (2) `apply_mask` is changed to reuse those same shared resample functions (assuming the mask is always label data) instead of its own bespoke resampling code, so all three commands (`downsample`, `upsample`, `apply_mask`) share one label-aware and one intensity-aware downsampling implementation. (3) The `bioio-ome-zarr` dependency is removed entirely (previously used only by `from_images` to build its initial pyramid), and the `ngff_zarr` dependency is scoped down to be used only by `migrate` (previously also used by `downsample`'s non-label path). All downsampling everywhere outside of `migrate` goes through a single `downsample_func` parameter defaulting to `skimage.transform.pyramid_gaussian`, and stays fully lazy end-to-end via `dask.array.map_blocks` (each chunk is resampled independently, so no array is ever fully materialized in memory) instead of eagerly computing whole arrays. Note: `apply_mask`'s existing `--output` flag (write the masked volume to a new path instead of masking in place) was already shipped separately and is out of scope here — this feature builds on top of that existing CLI surface without changing it."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Label-safe resampling everywhere a mask or segmentation dataset is resized (Priority: P1)

A user builds or extends multiscale pyramids for label/segmentation data (binary masks, multi-class annotations) using `downsample`, `upsample`, or `apply_mask`. In every one of these operations, they need the tool to never blend adjacent label values together into a new, previously-absent value — every voxel in the result must be one of the original label values.

**Why this priority**: Silently corrupting label data (e.g. averaging label `1` and label `2` into `1.5`, then truncating to something meaningless) invalidates downstream analysis without any visible error. This is a data-integrity guarantee, the highest-priority concern for a tool operating on scientific imaging data.

**Independent Test**: Build or extend a pyramid from a discrete-valued (e.g. binary 0/1) dataset using `--label`, or run `apply_mask` with a mask whose resolution doesn't match its volume; verify every value present in the newly built/resampled level is one already present in the source it was built from.

**Acceptance Scenarios**:

1. **Given** a label/segmentation OME-Zarr dataset, **When** the user runs `downsample --label`, **Then** every voxel in each newly added coarser level is exactly one of the values already present in the finer level it was built from.
2. **Given** a label/segmentation OME-Zarr dataset, **When** the user runs `upsample --label`, **Then** every voxel in each newly added finer level is exactly one of the values already present in the coarser level it was built from.
3. **Given** a mask dataset whose resolution doesn't match the volume it's being applied to, **When** the user runs `apply_mask`, **Then** the mask is resampled to match without ever introducing a value that wasn't already present in the mask.

---

### User Story 2 - Consistent `--label` option across downsample and upsample (Priority: P2)

A user who has learned `upsample`'s label-handling option expects `downsample` to expose the same option, and vice versa, without needing to learn two different flags or conventions for the same underlying concept.

**Why this priority**: Consistency reduces cognitive load and documentation burden, but the tool was already usable without it — this builds on User Story 1's correctness guarantee rather than replacing it.

**Independent Test**: Run `downsample --help` and `upsample --help`; confirm both expose an identically-named `--label` boolean option with equivalent behavior.

**Acceptance Scenarios**:

1. **Given** the CLI help output for both commands, **When** compared, **Then** both expose an identically-named `--label` boolean option meaning "treat this dataset as discrete label data rather than continuous intensity data," with equivalent effect on how new levels are built.

---

### User Story 3 - Building large pyramids without exhausting memory (Priority: P3)

A user converting a very large image stack/volume into an initial OME-Zarr pyramid (`from_images`), or extending an existing large dataset's pyramid (`downsample`), needs the tool to process the data in manageable pieces rather than requiring the entire dataset to fit in memory at once.

**Why this priority**: Keeps the tool usable as data sizes grow into the range typical of this tool's actual usage (large microscopy/CT volumes). Lower priority than correctness/consistency, since smaller datasets already worked either way.

**Independent Test**: Build or extend a pyramid from a volume whose total size exceeds a deliberately constrained memory budget; confirm the operation completes successfully by processing the data in bounded-size pieces rather than requiring the whole array in memory at any one point.

**Acceptance Scenarios**:

1. **Given** a volume whose full size exceeds a deliberately constrained memory budget, **When** the user runs `from_images` to build its initial pyramid (with one or more downsampled levels), **Then** the command completes successfully without ever requiring the whole volume, or a whole downsampled level, to be held in memory at a single point.

---

### Edge Cases

- What happens when a label dataset contains only a single distinct value (e.g. an all-zero mask)? The sole value must be preserved exactly through resampling.
- What happens when a dataset's dimension isn't evenly divisible by the downsampling factor (e.g. a size of 17)? The result's shape must be geometrically consistent with what was actually produced, and its recorded physical scale metadata must match that real shape exactly — never a shape that doesn't exist on disk.
- What happens when different distinct label values appear only in different regions of a large, chunked dataset? Every output voxel must still end up as one of the values present nearby, never an invented one, even when resampling proceeds region-by-region rather than examining the whole dataset at once.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `--label` option on both `downsample` (new) and `upsample` (renamed from its existing `--smooth <sigma>` option) with the same name and equivalent "treat this dataset as discrete label/segmentation data" meaning on both.
- **FR-002**: When resampling any dataset flagged as label/segmentation data (via `downsample --label`, `upsample --label`, or `apply_mask`'s mask resampling), the system MUST guarantee every output voxel is exactly one of the values already present in the corresponding source region — never a blended, averaged, or otherwise newly-invented value.
- **FR-003**: The system MUST use one shared underlying implementation for label-aware resampling across `downsample`, `upsample`, and `apply_mask`, rather than each command implementing its own separate logic.
- **FR-004**: The system MUST use one shared underlying implementation for continuous/intensity-value downsampling across every command that builds pyramid levels outside of `migrate` (`downsample`'s non-label path and `from_images`'s initial pyramid construction).
- **FR-005**: The system MUST NOT require any external third-party OME-Zarr-writing library (previously `bioio-ome-zarr`) to build a dataset's initial pyramid.
- **FR-006**: The system MUST continue to use its existing OME-NGFF spec-version-conversion library (`ngff_zarr`) only for the `migrate` command; no other command may depend on it.
- **FR-007**: Pyramid-building operations MUST process data in bounded-size pieces rather than requiring an entire dataset, or an entire pyramid level, to be loaded into memory at once.
- **FR-008**: The system MUST derive each pyramid level's recorded physical scale/resolution metadata from that level's own actual resulting shape, never from a shape value computed independently that could diverge from the real one (e.g. for dimensions not evenly divisible by the downsampling factor).

### Key Entities

- **Label/segmentation dataset**: An OME-Zarr array whose values are discrete category identifiers (e.g. a binary mask, a multi-class segmentation) rather than continuous measurements. Resampling it must never introduce a new, previously-absent value.
- **Intensity dataset**: An OME-Zarr array of continuous measurement values, where smoothing/blending across neighboring voxels during resampling is expected and desirable.
- **Pyramid level**: One resolution tier of a multiscale OME-Zarr dataset, with its own array shape and physical scale/resolution metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `downsample --label` or `upsample --label` on any label/segmentation dataset never produces an output voxel value absent from the corresponding source region, across all tested datasets.
- **SC-002**: `downsample --help` and `upsample --help` present the same `--label` option name and description intent, so a user familiar with one immediately understands the other.
- **SC-003**: Building a pyramid for a dataset far larger than the process's available memory succeeds, because memory use no longer scales with total dataset size.
- **SC-004**: Removing the previous third-party pyramid-writing dependency does not change any dataset's resulting OME-NGFF metadata shape or validity for any supported target spec version.

## Assumptions

- "Label/segmentation data" is assumed for `apply_mask`'s mask input in all cases (no user-facing flag to opt out) — a mask's values are meaningful discrete categories (foreground/background at minimum), never continuous data.
- Antialiased (Gaussian-pyramid-style) downsampling is the assumed default resampling strategy for continuous/intensity data everywhere outside of `migrate`, replacing whatever default the previous third-party library provided; no prior user-facing behavior guaranteed a specific different algorithm.
- `apply_mask`'s `--output` flag (write the masked volume to a new path instead of masking in place) already exists from prior, separate work and is unaffected by this feature — this spec's `apply_mask` scope is limited to *which resampling implementation* it uses internally, not its CLI surface.
- `downsample`/`upsample` already share an existing "add new multiscale levels" helper (array creation, metadata commit, rollback-on-failure) that this feature builds on rather than replaces.
