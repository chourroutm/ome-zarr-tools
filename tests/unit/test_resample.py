import dask
import dask.array as da
import numpy as np
import pytest

from ome_zarr_tools.core.errors import CliError
from ome_zarr_tools.core.resample import intensity_downsample, label_downsample


def _counting_lazy_array(data: np.ndarray, chunks) -> tuple[da.Array, dict]:
    """A lazy dask array backed by a delayed load that records how many times
    it was actually materialized -- lets a test assert a function never
    triggered computation just by being called."""
    calls = {"n": 0}

    def _load() -> np.ndarray:
        calls["n"] += 1
        return data

    lazy = da.from_delayed(dask.delayed(_load)(), shape=data.shape, dtype=data.dtype)
    return lazy.rechunk(chunks), calls


def _single_chunk_reference(func, data: np.ndarray, **kwargs):
    """Ground truth: run `func` on `data` as one single dask chunk (no
    possible seam), for comparison against a multi-chunk run."""
    return func(da.from_array(data, chunks=data.shape), **kwargs).compute()


def test_intensity_downsample_never_triggers_computation():
    data = np.random.default_rng(0).integers(0, 255, size=(16, 16, 16)).astype("uint8")
    lazy, calls = _counting_lazy_array(data, (8, 8, 8))

    result = intensity_downsample(lazy)

    assert isinstance(result, da.Array)
    assert calls["n"] == 0


def test_label_downsample_never_triggers_computation():
    mask = (np.random.default_rng(0).random((16, 16, 16)) > 0.5).astype("uint8")
    lazy, calls = _counting_lazy_array(mask, (8, 8, 8))

    result = label_downsample(lazy)

    assert isinstance(result, da.Array)
    assert calls["n"] == 0


def test_label_downsample_never_invents_a_value_not_in_the_source():
    mask = (np.random.default_rng(1).random((16, 16, 16)) > 0.5).astype("uint8")
    source_values = set(np.unique(mask).tolist())
    data = da.from_array(mask, chunks=(8, 8, 8))

    result = label_downsample(data).compute()

    assert set(np.unique(result).tolist()) <= source_values


def test_label_downsample_stays_within_source_values_when_labels_differ_per_chunk():
    """Different label values appearing only in different chunks must still
    never produce an invented value -- with the halo-aware default path, a
    block near the boundary *can* now see its neighbor's label inside its
    padding (that's the whole point of the fix), but every value it can ever
    see -- padded or not -- still traces back to a real source value, so this
    guarantee holds regardless.
    """
    labels = np.zeros((16, 16, 16), dtype="uint8")
    labels[:8] = 1  # label 1 confined to one chunk
    labels[8:] = 2  # label 2 confined to the other
    source_values = set(np.unique(labels).tolist())
    data = da.from_array(labels, chunks=(8, 16, 16))

    result = label_downsample(data).compute()

    assert set(np.unique(result).tolist()) <= source_values


def test_label_downsample_all_zero_mask_preserves_the_sole_value():
    mask = np.zeros((16, 16, 16), dtype="uint8")
    data = da.from_array(mask, chunks=(8, 8, 8))

    result = label_downsample(data).compute()

    assert set(np.unique(result).tolist()) == {0}


def test_intensity_downsample_odd_dimension_uses_ceiling_not_floor():
    """skimage.transform.pyramid_gaussian's real convention is ceiling
    division (17 -> 9), not the floor division (17 -> 8) a naive
    `size // factor` would give -- this must hold for the lazily-declared
    shape too, not just the eventually-computed one."""
    data = da.from_array(np.zeros((17, 17, 17), dtype="uint8"), chunks=(8, 8, 8))

    result = intensity_downsample(data)

    assert result.shape == (9, 9, 9)
    assert result.compute().shape == (9, 9, 9)


# ---------------------------------------------------------------------------
# Halo/overlap seam-fix tests (added when intensity_downsample/label_downsample
# gained cross-chunk-boundary Gaussian blending via dask.array.map_overlap).
# ---------------------------------------------------------------------------


def test_intensity_downsample_matches_single_chunk_reference_when_evenly_aligned():
    data = np.random.default_rng(2).integers(0, 255, size=(32, 32, 32)).astype("uint8")
    multi_chunk = da.from_array(data, chunks=(8, 8, 8))

    result = intensity_downsample(multi_chunk).compute()
    reference = _single_chunk_reference(intensity_downsample, data)

    assert result.shape == reference.shape
    assert np.array_equal(result, reference)


def test_intensity_downsample_matches_single_chunk_reference_with_irregular_margin_chunk():
    """Regression: shape (15,15,12) on chunks=(8,8,8) -> per-axis chunk sizes
    (8,7), (8,7), (8,4) -- ordinary, not-tiny remainder chunks. An earlier
    design (halo-aware smoothing followed by ratio-based
    skimage.transform.resize decimation) silently diverged from a no-seam
    reference here because resize's sampling grid depends on each block's own
    local in_size/out_size ratio, not the intended global factor -- fixed by
    switching decimation to plain fixed-stride subsampling."""
    data = np.random.default_rng(3).integers(0, 255, size=(15, 15, 12)).astype("uint8")
    multi_chunk = da.from_array(data, chunks=(8, 8, 8))
    assert multi_chunk.chunks == ((8, 7), (8, 7), (8, 4))

    result = intensity_downsample(multi_chunk).compute()
    reference = _single_chunk_reference(intensity_downsample, data)

    assert result.shape == reference.shape == (8, 8, 6)
    assert np.array_equal(result, reference)


def test_intensity_downsample_declared_shape_matches_computed_and_reference():
    """Guards dask's own lack of validation for map_overlap(trim=False,
    chunks=...): a mismatch between declared and actual shape is accepted
    silently, with no exception at construction or compute time."""
    data = np.random.default_rng(4).integers(0, 255, size=(15, 15, 12)).astype("uint8")
    multi_chunk = da.from_array(data, chunks=(8, 8, 8))

    result = intensity_downsample(multi_chunk)
    reference = _single_chunk_reference(intensity_downsample, data)

    assert result.shape == result.compute().shape == reference.shape


def test_intensity_downsample_tiny_boundary_chunk_matches_single_chunk_reference():
    data = np.random.default_rng(5).integers(0, 255, size=(17, 17, 17)).astype("uint8")
    multi_chunk = da.from_array(data, chunks=(8, 8, 8))

    result = intensity_downsample(multi_chunk).compute()
    reference = _single_chunk_reference(intensity_downsample, data)

    assert result.shape == reference.shape == (9, 9, 9)
    assert np.array_equal(result, reference)


def test_intensity_downsample_undersized_remainder_chunk_regression():
    """Shape (18,18,18) on chunks=(8,8,8) leaves a remainder of 2 per axis,
    which is smaller than the halo depth (3) -- exercises the trailing-chunk
    merge step. An earlier merge approach (da.overlap.ensure_minimum_chunksize)
    could silently turn a factor-aligned non-last chunk into a non-aligned
    one here, corrupting the result; fixed by a merge that only ever grows
    the trailing chunk, never redistributes an earlier one."""
    data = np.random.default_rng(6).integers(0, 255, size=(18, 18, 18)).astype("uint8")
    multi_chunk = da.from_array(data, chunks=(8, 8, 8))

    result = intensity_downsample(multi_chunk).compute()
    reference = _single_chunk_reference(intensity_downsample, data)

    assert result.shape == reference.shape == (9, 9, 9)
    assert np.array_equal(result, reference)


def test_intensity_downsample_rejects_non_factor_multiple_chunk_size():
    data = np.zeros((21, 8, 8), dtype="uint8")
    multi_chunk = da.from_array(data, chunks=(7, 8, 8))  # 7 is not a multiple of factor=2

    with pytest.raises(CliError):
        intensity_downsample(multi_chunk)


def test_intensity_downsample_custom_downsample_func_is_exempt_from_chunk_alignment():
    """The fallback (non-default downsample_func) path preserves today's
    unrestricted behavior -- no new chunk-size restriction imposed on it
    (chunks=(7,8,8), 7 not a multiple of factor=2, would be rejected on the
    default path)."""

    def _tracking_downsample_func(block, **kwargs):
        yield block[::2, ::2, ::2]

    data = np.zeros((21, 8, 8), dtype="uint8")
    multi_chunk = da.from_array(data, chunks=(7, 8, 8))

    result = intensity_downsample(multi_chunk, downsample_func=_tracking_downsample_func)

    # _downsampled_chunks ceils per-block, not per-axis: 3 chunks of 7 -> 3 of
    # ceil(7/2)=4, summing to 12 (not ceil(21/2)=11) -- pre-existing semantics.
    assert result.compute().shape == (12, 4, 4)


def test_intensity_downsample_custom_downsample_func_gets_unpadded_block():
    seen_shapes = []

    def _tracking_downsample_func(block, **kwargs):
        if block.size:  # dask also probes with an empty meta-array; ignore that call
            seen_shapes.append(block.shape)
        yield block[::2, ::2, ::2]

    data = np.zeros((16, 16, 16), dtype="uint8")
    multi_chunk = da.from_array(data, chunks=(8, 8, 8))

    intensity_downsample(multi_chunk, downsample_func=_tracking_downsample_func).compute()

    assert seen_shapes and all(shape == (8, 8, 8) for shape in seen_shapes)


def test_label_downsample_matches_single_chunk_reference_across_chunk_boundary():
    labels = np.zeros((15, 15, 12), dtype="uint8")
    labels[:9] = 1
    labels[9:] = 2
    labels[:, :, 10:] = 3  # a third label confined to the small size-4 remainder chunk
    multi_chunk = da.from_array(labels, chunks=(8, 8, 8))
    assert multi_chunk.chunks == ((8, 7), (8, 7), (8, 4))

    result = label_downsample(multi_chunk).compute()
    reference = _single_chunk_reference(label_downsample, labels)

    assert result.shape == reference.shape == (8, 8, 6)
    assert np.array_equal(result, reference)


def test_label_downsample_thin_sliver_near_true_boundary_matches_single_chunk_reference():
    """Regression: a thin label region sitting right at the true array
    boundary, inside an irregular remainder chunk, combined with a wider
    smoothing sigma -- an earlier ratio-based-resize decimation design could
    flip this label's value over an entire boundary face."""
    labels = np.zeros((15, 15, 12), dtype="uint8")
    labels[14:, :, :] = 7  # thin sliver, last x-slice only
    multi_chunk = da.from_array(labels, chunks=(8, 8, 8))

    result = label_downsample(multi_chunk, smooth=1.0).compute()
    reference = _single_chunk_reference(label_downsample, labels, smooth=1.0)

    assert result.shape == reference.shape
    assert np.array_equal(result, reference)


def test_label_downsample_declared_shape_matches_computed_and_reference():
    labels = np.random.default_rng(7).integers(0, 4, size=(15, 15, 12)).astype("uint8")
    multi_chunk = da.from_array(labels, chunks=(8, 8, 8))

    result = label_downsample(multi_chunk)
    reference = _single_chunk_reference(label_downsample, labels)

    assert result.shape == result.compute().shape == reference.shape


def test_label_downsample_tiny_boundary_chunk_matches_single_chunk_reference():
    labels = np.random.default_rng(8).integers(0, 3, size=(17, 17, 17)).astype("uint8")
    multi_chunk = da.from_array(labels, chunks=(8, 8, 8))

    result = label_downsample(multi_chunk).compute()
    reference = _single_chunk_reference(label_downsample, labels)

    assert result.shape == reference.shape == (9, 9, 9)
    assert np.array_equal(result, reference)


def test_label_downsample_undersized_remainder_chunk_regression():
    labels = np.random.default_rng(9).integers(0, 3, size=(18, 18, 18)).astype("uint8")
    multi_chunk = da.from_array(labels, chunks=(8, 8, 8))

    result = label_downsample(multi_chunk).compute()
    reference = _single_chunk_reference(label_downsample, labels)

    assert result.shape == reference.shape == (9, 9, 9)
    assert np.array_equal(result, reference)


def test_intensity_downsample_single_chunk_axis_smaller_than_halo_depth():
    """Regression: chaining repeated downsampling (e.g. `downsample
    --num_levels N`, where each level's output feeds the next call) can
    shrink an axis down to a single chunk smaller than the halo depth well
    before N iterations are done. There's no predecessor chunk left for
    `_merge_undersized_trailing_chunk` to merge into at that point -- must
    fall back to zero halo on that axis instead of failing, since a single
    chunk already sees that whole axis's true extent directly (no seam
    possible)."""
    data = np.random.default_rng(10).integers(0, 255, size=(2, 8, 8)).astype("uint8")
    single_chunk_axis0 = da.from_array(data, chunks=(2, 8, 8))  # depth would be 3 > 2

    result = intensity_downsample(single_chunk_axis0).compute()
    reference = _single_chunk_reference(intensity_downsample, data)

    assert result.shape == reference.shape == (1, 4, 4)
    assert np.array_equal(result, reference)


def test_label_downsample_single_chunk_axis_smaller_than_halo_depth():
    labels = np.random.default_rng(11).integers(0, 3, size=(2, 8, 8)).astype("uint8")
    single_chunk_axis0 = da.from_array(labels, chunks=(2, 8, 8))

    result = label_downsample(single_chunk_axis0).compute()
    reference = _single_chunk_reference(label_downsample, labels)

    assert result.shape == reference.shape == (1, 4, 4)
    assert np.array_equal(result, reference)
