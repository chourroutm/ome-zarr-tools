# Quickstart: Validating Config Env-Var Files

Prerequisites: repo checked out, `.venv` active (`source .venv/bin/activate`), package editable-installed (`uv pip install -e . --no-deps`).

## 1. Set a value, confirm it's stored

```bash
ome-zarr-tools config set /tmp/settings.env OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=128
ome-zarr-tools config show /tmp/settings.env
```

Expected: `OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=128` appears in both outputs. This alone doesn't yet prove the feature works — it proves the old behavior still trivially works (dead round-trip). Step 2 is the real test.

## 2. Confirm the value actually changes a command's default (User Story 1)

```bash
mkdir -p /tmp/stack && for i in 0 1 2; do
  python -c "import numpy as np, imageio.v3 as iio; iio.imwrite(f'/tmp/stack/{$i:03d}.tif', np.zeros((8,8), dtype='uint8'))"
done
ome-zarr-tools --env-file /tmp/settings.env from_images --stack_dir /tmp/stack --voxel_size 1.0 /tmp/out.zarr
```

Expected: the run succeeds and the resulting `/tmp/out.zarr`'s level-0 chunk size is `128` (not the built-in default `64`) — inspect with `ome-zarr-tools inspect /tmp/out.zarr` and check the reported chunk shape.

## 3. Confirm an explicit flag still overrides (FR-007)

```bash
ome-zarr-tools --env-file /tmp/settings.env from_images --stack_dir /tmp/stack --voxel_size 1.0 --chunk_size 32 /tmp/out2.zarr
ome-zarr-tools inspect /tmp/out2.zarr
```

Expected: chunk size is `32`, not `128` — the explicit `--chunk_size 32` won.

## 4. Confirm a shared variable applies to both commands it targets (FR-006)

```bash
ome-zarr-tools config set /tmp/settings.env OME_ZARR_TOOLS_TARGET_VERSION=0.4
ome-zarr-tools --env-file /tmp/settings.env from_images --stack_dir /tmp/stack --voxel_size 1.0 /tmp/out3.zarr
ome-zarr-tools --env-file /tmp/settings.env migrate /tmp/out3.zarr --target_version 0.5 --output /tmp/out3_migrated.zarr
```

Expected: `/tmp/out3.zarr` is written at spec 0.4 (Zarr v2) without `--target_version` being passed explicitly to `from_images`; the `migrate` call's explicit `--target_version 0.5` overrides the same shared variable for that run.

## 5. Confirm the `num_levels` variables are NOT accidentally shared (FR-006)

```bash
ome-zarr-tools config set /tmp/settings.env OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS=3
ome-zarr-tools --env-file /tmp/settings.env upsample /tmp/out3.zarr --num_levels 1
```

Expected: `upsample` adds exactly 1 finer level (its own default/explicit value), unaffected by `downsample`'s separately-scoped variable.

## 6. Confirm unrecognized-key reporting is scoped correctly (FR-016/SC-006)

```bash
printf 'OME_ZARR_TOOLS_TYPO_OPTION=1\nAWS_ACCESS_KEY_ID=fake\n' >> /tmp/settings.env
ome-zarr-tools config show /tmp/settings.env
```

Expected: `OME_ZARR_TOOLS_TYPO_OPTION` is flagged as an unrecognized/error-level message; `AWS_ACCESS_KEY_ID` is not mentioned at all.

## 7. Confirm duplicate-key handling (FR-015)

```bash
printf 'OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.1\nOME_ZARR_TOOLS_APPLY_MASK_THRESHOLD=0.9\n' > /tmp/dup.env
ome-zarr-tools config show /tmp/dup.env
```

Expected: a duplicate-key warning naming `OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD`; the displayed/effective value is `0.9` (last wins).

## 8. Confirm the removed/renamed options (FR-011/FR-012/FR-013)

```bash
ome-zarr-tools apply_mask --help | grep -c temporary_upsample   # expect: 0
ome-zarr-tools inspect --help | grep json                       # expect: --json flag listed
ome-zarr-tools from_images --help | grep num_levels              # expect: listed; num_downsampling gone
```

## 9. TUI spot-check (manual or headless Textual test)

```bash
ome-zarr-tools --env-file /tmp/settings.env interactive --tui
```

Expected: the main menu shows a warning row below the command list naming `OME_ZARR_TOOLS_TYPO_OPTION` (from step 6, if still present in the file); opening `config` shows the `ENV_FILE` path field and a plain-text editor (no JSON), with default-entry buttons inserting `KEY=VALUE` lines.

## Cleanup

```bash
rm -rf /tmp/settings.env /tmp/dup.env /tmp/stack /tmp/out.zarr /tmp/out2.zarr /tmp/out3.zarr /tmp/out3_migrated.zarr
```
