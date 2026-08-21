# Feature Specification: Downsample and Upsample commands

**Feature Branch**: `007-downsample-upsample-commands`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Add two new commands: downsample - to add extra multiscale layers - and upsample - create extra multiscale layers but meant for masks only. downsample and upsample have an optional output zarr, otherwise do in-place. upsample has an optional smooth parameter. upsample may require to reorder the multiscale metadata if the path 0 is already set. both have a number of levels to add, that has value 1 if unset."

## Clarifications

### Session 2026-08-14

- Q: What should upsample's optional smoothing parameter actually do to the newly upsampled mask levels? → A: Smooth then re-snap every voxel to the nearest original discrete label value, so the output always stays a valid mask.
- Q: Should downsample/upsample validate that the input data actually looks like the expected kind (e.g. upsample checking for integer/label-typed data since it's mask-only), or just trust the user's input like this tool's other commands already do? → A: Trust the user, no extra check -- matches every other command in this tool.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extend a pyramid with coarser levels (Priority: P1)

A user has an OME-Zarr dataset whose multiscale pyramid doesn't go coarse enough for their downstream tool (e.g. a viewer that expects more zoom-out levels, or a workflow that needs a very low-resolution overview level to run quickly). They run `downsample` on the dataset to add one or more additional, coarser resolution levels below the existing coarsest level, either updating the dataset directly or writing the extended result to a new location.

**Why this priority**: This is the more broadly useful of the two commands (works on any dataset, not just masks) and has no dependency on the other command.

**Independent Test**: Run `downsample` on a dataset with an existing 2-level pyramid, with no options set, and confirm the result has 3 levels, the new level is half the resolution of the previous coarsest level, and the dataset's own on-disk pixel data for the existing levels is unchanged.

**Acceptance Scenarios**:

1. **Given** a valid OME-Zarr dataset, **When** the user runs `downsample` with no options, **Then** exactly one new, coarser level is added below the existing coarsest level, in place.
2. **Given** the same dataset, **When** the user runs `downsample` with a number-of-levels value of 3, **Then** exactly 3 new, progressively coarser levels are added.
3. **Given** the same dataset, **When** the user runs `downsample` with an output path, **Then** the original dataset is left completely unchanged and the extended pyramid is written to the new path instead.
4. **Given** a dataset whose metadata does not validate, **When** the user runs `downsample`, **Then** the command fails with a clear error and nothing is written.

---

### User Story 2 - Extend a mask's pyramid with finer levels (Priority: P2)

A user has a label/mask dataset (e.g. a segmentation produced at a coarser resolution than the intensity image it annotates) and needs it to also provide finer resolution levels so it lines up with a higher-resolution intensity dataset. They run `upsample` to add one or more additional, finer resolution levels above the existing finest level, optionally smoothing the result, either updating the dataset directly or writing the extended result to a new location.

**Why this priority**: Narrower in scope (masks only) and depends on the same shared "add N levels, optional output, in-place by default" behavior `downsample` already establishes.

**Independent Test**: Run `upsample` on a mask dataset with an existing single-level pyramid, with no options set, and confirm the result has 2 levels, the new level is double the resolution of the previous finest level, and it is positioned as the new finest level.

**Acceptance Scenarios**:

1. **Given** a valid mask dataset, **When** the user runs `upsample` with no options, **Then** exactly one new, finer level is added above the existing finest level, in place.
2. **Given** the same dataset, **When** the user runs `upsample` with a number-of-levels value of 2, **Then** exactly 2 new, progressively finer levels are added.
3. **Given** the same dataset, **When** the user runs `upsample` with an output path, **Then** the original dataset is left completely unchanged and the extended pyramid is written to the new path instead.
4. **Given** the same dataset's existing finest level is listed first in the multiscale metadata, **When** `upsample` adds a new, finer level, **Then** the new level is listed first instead and the previous finest level moves later in the list — every level's own on-disk pixel data is otherwise unchanged.
5. **Given** the user supplies the smoothing option, **When** `upsample` builds each new finer level, **Then** the smoothing is applied per FR-010 below.

---

### Edge Cases

- What happens when the requested output path already exists? Rejected before anything is written, matching `migrate --output`'s existing behavior.
- What happens when the dataset has no multiscale metadata at all, or it's structurally invalid? Rejected with a clear error before any levels are added, matching `migrate`'s existing validate-first behavior.
- What happens if a level being added would have a dimension smaller than 1 pixel along any axis? Rejected with a clear error rather than silently producing a degenerate/empty level.
- What happens to `upsample`'s new on-disk array paths (not to be confused with position in the metadata list)? They get freshly chosen identifiers that don't collide with any existing level's path — no existing level's on-disk data is renamed or moved, only the metadata list's *order* changes (FR-011).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to run `downsample` on an existing OME-Zarr dataset to add one or more new, coarser multiscale levels below its existing coarsest level.
- **FR-002**: Users MUST be able to run `upsample` on an existing OME-Zarr mask/label dataset to add one or more new, finer multiscale levels above its existing finest level.
- **FR-003**: Both commands MUST accept an optional number-of-levels-to-add value; when not given, exactly 1 level MUST be added.
- **FR-004**: Both commands MUST accept an optional output path. When given, the extended pyramid MUST be written there and the original dataset MUST be left completely unchanged. When not given, the original dataset MUST be updated in place.
- **FR-005**: When updating in place, both commands MUST back up the dataset's existing root metadata first and MUST leave the original dataset completely untouched if the operation fails partway, matching the existing `migrate` command's in-place safety behavior.
- **FR-006**: When the requested output path already exists, both commands MUST fail with a clear error before writing anything, matching `migrate --output`'s existing behavior.
- **FR-007**: Both commands MUST reject a dataset with missing or invalid multiscale metadata, with a clear error, before adding any levels.
- **FR-008**: `downsample`'s new levels MUST each be built from the previous coarsest level, each halving resolution along every spatial axis relative to the previous one, consistent with this tool's existing pyramid-building convention (`from_images --num_downsampling`).
- **FR-009**: `upsample`'s new levels MUST each be built from the previous finest level, each doubling resolution along every spatial axis relative to the previous one, using an upsampling approach that preserves valid discrete label values (never introducing fractional/interpolated values between distinct labels).
- **FR-010**: `upsample`'s optional smoothing parameter, when given, MUST soften label boundaries and then re-snap every voxel to the nearest original discrete label value, so the result is always a valid mask (never leaving continuous/anti-aliased values). When not given, no smoothing is applied.
- **FR-011**: When `upsample` adds a new finest level, the multiscale metadata's dataset list MUST be reordered so the new finest level is listed first; every other level's existing on-disk array data MUST remain unchanged (only the metadata list's order and the newly added levels are affected).
- **FR-012**: Neither command validates that the input data "looks like" the expected kind (e.g. `upsample` does not check for integer/label-typed data) — both trust the dataset given, the same way every other command in this tool trusts its input, validating only the OME-Zarr metadata's own structural correctness (FR-007).

### Key Entities

- **Multiscale pyramid**: The ordered set of resolution levels an OME-Zarr dataset provides, described by its `multiscales` metadata (one entry per level: an on-disk array path plus its scale/resolution). `downsample` extends this set with coarser levels; `upsample` extends it with finer levels.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `downsample` or `upsample` with no options adds exactly 1 new level, 100% of the time, verified against the dataset's resulting multiscale metadata.
- **SC-002**: Running either command with an output path leaves the original dataset byte-for-byte unchanged, verified for every existing file in the original dataset.
- **SC-003**: Running either command in place, when it fails partway through, leaves the original dataset exactly as it was before the command ran, verified the same way `migrate`'s existing in-place failure handling already is.
- **SC-004**: After `upsample` adds a new finest level, that level is always the first entry in the dataset's multiscale metadata, verified against the resulting metadata.

## Assumptions

- Each added level scales resolution by a factor of 2 per axis relative to its immediate neighbor (halving for `downsample`, doubling for `upsample`), matching this tool's existing pyramid convention (`from_images --num_downsampling`) rather than exposing a configurable scale factor.
- `upsample`'s new on-disk array paths are freshly chosen identifiers that don't collide with any existing level's path; per the OME-NGFF spec, a dataset's `path` value is an arbitrary string identifier with no ordering meaning of its own, so reordering "which level is finest" only ever means reordering the *metadata list*, never renaming/moving any existing level's on-disk data.
- Neither command exposes the underlying downsampling/upsampling algorithm as a user-facing choice — each picks one sensible, fixed approach internally (as `from_images` already does for its own pyramid building), keeping the command's options limited to exactly what was requested (levels to add, output path, and — `upsample` only — smoothing).
