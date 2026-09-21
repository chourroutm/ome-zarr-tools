# Quickstart: validating the unified resampling feature

Prerequisites: repo checked out, `.venv` set up per `pyproject.toml` (`pip install -e ".[dev]"`), working directory the repo root.

## 1. Static checks (constitution Quality Gates)

```bash
ruff check src/ome_zarr_tools tests
mypy src/ome_zarr_tools
```

Expect zero issues from both.

## 2. Confirm the dependency boundary landed correctly

```bash
grep -rn "bioio" src/ tests/ pyproject.toml        # expect: zero hits
grep -rn "ngff_zarr\|ngff-zarr" src/                # expect: hits only in commands/migrate.py
```

## 3. `downsample --label` never invents a label value (US1, FR-002)

```python
import numpy as np, zarr
from click.testing import CliRunner
from ome_zarr_tools.commands.downsample import downsample

# build a small binary-label fixture at path via the test suite's own
# sample_mask_zarr fixture (see tests/conftest.py), then:
runner = CliRunner()
result = runner.invoke(downsample, [str(mask_zarr_path), "--label"])
assert result.exit_code == 0

group = zarr.open_group(str(mask_zarr_path), mode="r")
new_level_values = set(np.unique(group["<new level path>"][:]).tolist())
assert new_level_values <= {0, 1}   # never a value absent from the source
```

Run the equivalent existing/new automated tests directly:

```bash
pytest tests/integration/test_downsample.py -k label -v
pytest tests/integration/test_upsample.py -k label -v
pytest tests/integration/test_apply_mask.py -v
```

## 4. `downsample --help` / `upsample --help` show the same `--label` option (US2, SC-002)

```bash
python -m ome_zarr_tools downsample --help | grep -A2 -- '--label'
python -m ome_zarr_tools upsample --help | grep -A2 -- '--label'
```

Expect matching option name and description intent in both.

## 5. `from_images` builds a pyramid without requiring the whole volume in memory (US3, FR-007, SC-003)

Not practical to literally exhaust process memory in a quick check; instead confirm the *mechanism*: `core.resample.intensity_downsample`/`label_downsample` accept and return lazy `dask.array.Array` (never call `.compute()` internally), and `core.pyramid.write_new_pyramid` issues exactly one combined `da.store()` call across all levels of a single invocation (not one per level) — both asserted directly by unit tests:

```bash
pytest tests/unit/test_resample.py -v
pytest tests/unit/test_pyramid.py -k write_new_pyramid -v
```

## 6. Metadata shape/validity unaffected by the dependency removal (SC-004)

```python
import json, tempfile, os
import dask.array as da, numpy as np, zarr
from ome_zarr_tools.core.pyramid import write_new_pyramid

d = tempfile.mkdtemp()
p = os.path.join(d, "out.zarr")
arr = da.from_array(np.zeros((16, 32, 32), dtype="uint8"), chunks=(8, 8, 8))
write_new_pyramid(
    p, arr, 1,
    axes_names=["z", "y", "x"], axes_types=["space"] * 3, axes_units=["micrometer"] * 3,
    voxel_size=[1.0, 1.0, 1.0], chunk_shape=(8, 8, 8), shard_shape=None,
    zarr_format=2, image_name="Image",
)
g = zarr.open_group(p, mode="r")
print(json.dumps(dict(g.attrs), indent=2))  # inspect: multiscales shape, no "omero" block
```

Repeat with `zarr_format=3` and confirm `attrs["ome"]["version"] == "0.5"`. Also spot-check an odd, non-power-of-two shape (e.g. `(17, 17, 17)`) and confirm the recorded `scale` for level 1 matches the *actual* on-disk level-1 shape, not a value computed from `math.floor(17/2) == 8`.

## 7. Full regression suite

```bash
pytest -q
```

`tests/conftest.py`'s `_write_ome_zarr()` fixture helper backs ~19 other test files beyond this feature's own — this is the primary regression gate for the dependency swap. Run in the background with a generous timeout if the environment's default command timeout is short; a small number of Textual-TUI async tests are known to be flaky under load in this environment (thread exhaustion running many in one process) — re-run any such failure individually before treating it as a real regression.
