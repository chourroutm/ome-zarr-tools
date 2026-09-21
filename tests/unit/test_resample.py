import dask
import dask.array as da
import numpy as np

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
    never produce an invented value -- label_downsample() decomposes each
    block using only that block's own local label set (core/resample.py),
    so this must hold even without any single chunk seeing the full set.
    """
    labels = np.zeros((16, 16, 16), dtype="uint8")
    labels[:8] = 1  # label 1 confined to one chunk
    labels[8:] = 2  # label 2 confined to the other -- no chunk ever sees both
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
