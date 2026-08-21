# Phase 1 Data Model: Downsample and Upsample commands

No new persistent entity types are introduced — both commands extend the
same `multiscales` metadata shape every other command in this codebase
already reads/writes (`io/ome_metadata.py`).

## Pyramid Level (existing shape, extended)

**Represents**: One resolution level of a dataset's multiscale pyramid — an
on-disk Zarr array plus its entry in `multiscales[0].datasets`:

```python
{"path": "<str>", "coordinateTransformations": [
    {"type": "scale", "scale": [z, y, x]},
    {"type": "translation", "translation": [tz, ty, tx]},  # optional
]}
```

**Relationships**: `datasets[0]` is this codebase's own convention for "the
finest/reference level" (relied on by `fix_metadata.py::build_proposed_multiscales`
and `ome_metadata.py::add_half_pixel_translations`) — not a spec requirement,
but one both new commands must preserve.

**Lifecycle for `downsample`**: existing coarsest level (`datasets[-1]`, by
this codebase's own list-order convention) → wrapped as an `NgffImage` →
`ngff_zarr.to_multiscales(image, scale_factors=[2**i for i in range(1, n+1)])`
→ `n` new, coarser `NgffImage`s → each written to a fresh array path and
appended to `datasets` (list order: existing entries, then new ones,
coarsest last).

**Lifecycle for `upsample`**: existing finest level (`datasets[0]`) → read as
a dask array → `n` new, finer levels built by chaining
`dask.array.repeat(arr, 2, axis=i)` over every spatial axis, each new level
built from the previous (each level upsamples the one before it, not always
the original) → each optionally smoothed (see below) → each written to a
fresh array path and **prepended** to `datasets` (list order: new levels
finest-to-least-fine, then the previous entries unchanged — the new
overall-finest level ends up at `datasets[0]`).

## Smoothed Label Level (new, `upsample --smooth` only)

**Represents**: The result of softening one upsampled level's label
boundaries while keeping every voxel a valid, original discrete label value.

**Representation**: Computed from one upsampled level (a NumPy array once
materialized):

```python
labels = np.unique(level)
channels = np.stack([
    scipy.ndimage.gaussian_filter((level == label).astype(float), sigma)
    for label in labels
])
smoothed_level = labels[np.argmax(channels, axis=0)]
```

**Relationships**: Only ever derived from one already-upsampled level
(never from an original/existing level directly) — smoothing is applied
per new level, not once to the whole result.

**Lifecycle**: Upsampled level (dask, lazy) → `.compute()` (materialize,
needed for cross-voxel Gaussian context) → per-label channel decomposition →
per-channel `gaussian_filter` → `argmax` re-snap → written to the array's
target path in place of the un-smoothed result. Only runs when `--smooth`
is given; otherwise the plain repeated/upsampled level is written directly.

## Output Destination (shared with `migrate`)

**Represents**: Where the extended dataset ends up — the original path
(in-place) or a new path (`--output`).

**Representation**: `core/zarr_path.py::validate_output_path(output_path)`
(moved here from `migrate.py` so `downsample`/`upsample` and `migrate` share
one definition) raises `CliError` if `output_path` is given and already
exists. When given, `shutil.copytree(source, output_path)` runs *before* any
new levels are built, so every subsequent step operates only on the copy —
the original is never opened for writing in this mode.

**Lifecycle**: Unchanged from `migrate`'s existing `--output` behavior
(added directly to `migrate.py` earlier, outside a formal spec cycle), just
relocated so it has one shared definition instead of three duplicated ones.
