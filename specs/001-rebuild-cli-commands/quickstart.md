# Quickstart: Validate the Rebuilt `ome-zarr-tools` CLI

Prerequisites: a working checkout of this branch, Python ≥3.10, and `pip install -e .[dev]` run from the repo root (installs the runtime deps from `pyproject.toml` plus `pytest`/`ruff`/`mypy`).

## 1. Automated test suite (covers all scenarios below)

```bash
pytest tests/ -q
```
Expected: all tests pass, including at least one success-path and one failure-path test per command (FR-008), satisfying SC-004 and SC-006.

## 2. User Story 1 — existing commands still work end-to-end

```bash
# Convert a small synthetic stack (fixture under tests/fixtures/stack/) to OME-Zarr
ome-zarr-tools from_images --stack_dir tests/fixtures/stack --voxel_size 1.0 --voxel_size 1.0 --voxel_size 2.0 /tmp/demo.zarr

# Extract a crop from it
ome-zarr-tools extract /tmp/demo.zarr --corner 0 0 0 --size 32 32 16 --output /tmp/crop.ome.tif

# Fix/inspect its metadata (answer prompts, confirm write)
ome-zarr-tools fix_metadata /tmp/demo.zarr

# Apply a mask (fixture under tests/fixtures/mask.zarr/)
ome-zarr-tools apply_mask --volume /tmp/demo.zarr --mask tests/fixtures/mask.zarr

# Configuration round-trip
ome-zarr-tools config set --project /tmp compression=zstd
ome-zarr-tools config show --project /tmp
ome-zarr-tools config reset --project /tmp compression
```
Expected: each command exits `0`; `/tmp/demo.zarr` validates with `ome-zarr-models`; see [contracts/cli-contract.md](./contracts/cli-contract.md) for exact option behavior. Validates SC-001.

## 3. User Story 2 — interactive mode

```bash
ome-zarr-tools interactive
```
Expected: a numbered menu of all six other subcommands; selecting `from_images` and answering its prompts (using the same fixture as above) produces the same `/tmp/demo.zarr` result as the direct invocation, and the tool prints the equivalent direct-CLI command line before running it. Cancelling (Ctrl-C or "no" at the final confirmation) leaves no file on disk. Validates SC-002 and FR-011.

## 4. User Story 3 — migrate

```bash
# Fixture: an OME-Zarr dataset written at spec version 0.4 (Zarr v2 storage, per the spec)
ome-zarr-tools migrate tests/fixtures/legacy_v2.zarr --target_version 0.5
```
Expected: the tool reports the source version (`0.4`, on Zarr v2) and target version (`0.5`, which implies Zarr v3 — see `data-model.md` § OME-Zarr Dataset), asks for confirmation, then:
- validates the migrated dataset (metadata **and** storage) with `ome-zarr-models`,
- leaves a metadata backup file next to the dataset,
- and produces pixel data identical (checksum-equal) to the source.

Re-running the same command immediately after should print "already current" and make no further changes (FR-012). Validates SC-003.

## 5. User Story 4 — inspect

```bash
ome-zarr-tools inspect /tmp/demo.zarr
ome-zarr-tools inspect /tmp/demo.zarr --format json
```
Expected: the text report lists, per resolution level, shape/dtype/chunk shape/shard shape/stored size/logical size, plus dataset-wide totals; the `--format json` output contains the same data as a parseable `Inspection Report` (see `data-model.md`). Neither invocation modifies `/tmp/demo.zarr` (compare a checksum of the store before/after). Validates SC-007 and FR-017–FR-019.

## 6. Failure-path spot check (SC-004)

```bash
ome-zarr-tools extract /nonexistent/path.zarr
echo $?   # expect non-zero
ome-zarr-tools config set /tmp compression=zstd   # missing --user/--project
echo $?   # expect non-zero, with a clear message, not a traceback
```

## 7. Reproducible install (SC-005)

```bash
pip install -e . --dry-run 2>&1 | tee /tmp/install-1.log
pip install -e . --dry-run 2>&1 | tee /tmp/install-2.log
diff /tmp/install-1.log /tmp/install-2.log   # expect no diff in resolved versions
```
