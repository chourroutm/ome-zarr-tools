# Phase 1 Contract: `core/resample.py` and `core/pyramid.py::write_new_pyramid` (internal API)

This feature's real "interface contract" is internal — a shared Python API three commands (`downsample`, `upsample` partially, `apply_mask`) call into, plus one command (`from_images`) that calls a new pyramid-writing function built on top of it. Documented here since `commands/*.py` callers depend on these signatures holding across the whole codebase.

## `core/resample.py`

### `nearest_upsample(array: da.Array, factor: int = 2) -> da.Array`

*(Pre-existing, unaffected by this feature — documented for completeness since `apply_mask` newly depends on it directly.)* Exact `factor`x nearest-neighbor expansion per axis, lazy (`da.repeat`). Safe for both label and intensity data (never interpolates).

### `intensity_downsample(data: da.Array, factor: int = 2, *, downsample_func: Callable[..., Iterable[npt.NDArray]] = skimage.transform.pyramid_gaussian) -> da.Array`

**NEW.** Downsamples continuous/intensity data by `factor` per axis, lazily. Each dask block is passed to `downsample_func(block, max_layer=1, downscale=factor, preserve_range=True)`, taking the last (most-downsampled) yielded array. No per-label decomposition — blending is correct/expected for intensity data.

**Contract**:
- Input and output are both lazy `dask.Array`; calling this never triggers computation.
- Output shape per axis, per block: `math.ceil(block_size / factor)` (matches `skimage.transform.pyramid_gaussian`'s own convention, verified empirically — **not** `floor`).
- `downsample_func` must accept `(array, max_layer, downscale, preserve_range)` and return an iterable of progressively-downsampled arrays (as `skimage.transform.pyramid_gaussian`/`pyramid_laplacian` do); only the last element is used.

### `label_downsample(data: da.Array, factor: int = 2, *, smooth: float | None = None, downsample_func: Callable[..., Iterable[npt.NDArray]] = skimage.transform.pyramid_gaussian) -> da.Array`

**Changed** (previously eager/`npt.NDArray`-based; now lazy/`da.Array`-based, same external call signature otherwise). Downsamples label/segmentation data by `factor` per axis, lazily. Each dask block is decomposed into one boolean channel per distinct label value *present in that block*, each channel independently downsampled via `downsample_func(channel, max_layer=1, downscale=factor, sigma=smooth, preserve_range=True)`, then every voxel re-snapped to the label of its highest-probability channel (`argmax`).

**Contract**:
- Input and output are both lazy `dask.Array`.
- Every output voxel is guaranteed to be one of the values present in its corresponding source block's neighborhood — never a new, previously-absent value (FR-002).
- Same output-shape convention as `intensity_downsample` (ceiling division per block).

## `core/pyramid.py`

### `write_new_pyramid(path: Path, arr: DaskArray, num_downsampling: int, *, axes_names, axes_types, axes_units, voxel_size, chunk_shape, shard_shape, zarr_format, image_name, downsample_func=skimage.transform.pyramid_gaussian) -> None`

**NEW.** Creates a brand-new OME-Zarr group at `path` from scratch (overwriting anything already there — matches the previous `bioio_ome_zarr` writer's own always-overwrite semantics). Level 0 is written directly (lazily) from `arr`. Each of `num_downsampling` further levels is built by chaining `intensity_downsample` on the previous level, with **shape and scale metadata both derived from that same real lazy output** (never an independently precomputed shape — see `research.md`'s bug writeup). All levels are written via one combined `da.store()` call, not one per level (see `research.md`'s batching decision).

**Contract**:
- Writes bare-bones multiscales metadata only: a single `"scale"` `coordinateTransformations` entry per dataset, no `"translation"`, no `"omero"` block. Callers wanting translations (e.g. `from_images`) add them afterward via the existing `io.ome_metadata.add_half_pixel_translations` + `write_multiscales` — this function deliberately does not call them itself.
- `zarr_format=2` writes the bare top-level `attrs["multiscales"]` shape (with `"version": "0.4"`); `zarr_format=3` writes the nested `attrs["ome"]["multiscales"]` shape (with `"version": "0.5"`) — matching `io.ome_metadata.read_multiscales`'s existing dual-shape support.
- Sets an explicit zstd/bitshuffle Blosc compressor (matching the previous writer's own explicit choice) rather than relying on `zarr`'s own default.
- `dimension_names` is set on created arrays only for `zarr_format=3` (matches `core.pyramid.commit_new_levels`'s existing convention).

### `commit_new_levels(...)` (existing signature unchanged; internal batching changed)

**Changed internally** (no change to its external signature or existing callers' code): the per-level `create_array` + collision-retry loop is unchanged, but the actual `da.store()` call is now issued once, combined across every level in `new_levels`, after the loop — not once per level inside it. Existing collision-retry and rollback-on-failure behavior (`_remove_arrays`, `restore_attrs`) is preserved exactly.
