# OME-Zarr Tools CLI

Command-line tools for working with OME-Zarr multiscale datasets (also known as OME-NGFF). New datasets are written against [the OME-Zarr 0.5 specification](https://ngff.openmicroscopy.org/0.5/index.html) by default (Zarr v3 storage); `migrate` can also target the earlier 0.4 specification (Zarr v2 storage).

## Installation

```bash
pip install -e ".[dev]"
```

This installs the pinned runtime dependencies plus `pytest`, `ruff`, and `mypy`. See `pyproject.toml` for exact version constraints.

To work with datasets on Google Cloud Storage or S3 (`gs://...`, `s3://...` paths), also install the `remote` extra:

```bash
pip install -e ".[remote]"
```

This adds `gcsfs`/`s3fs` (via `zarr[remote]`). Without it, remote paths are still accepted by the CLI but fail with a clear error when the command tries to open the store.

## Usage

```bash
ome-zarr-tools [--env-file PATH] [subcommand] [OPTIONS]
```

`--env-file PATH` (optional, top-level) supplies default option values for the subcommand run from a `KEY=VALUE` settings file managed by `config` (see below) — an explicit flag on the command line always overrides it.

Any `ZARR_PATH`/`--volume`/`--mask` argument accepts either a local path or a remote store URL (`gs://...`, `s3://...`) — the `remote` extra above must be installed for the URL to actually open. `inspect`/`extract` are read-only and work well against remote data; `fix_metadata`/`migrate`/`apply_mask` write to the store, and remote write support depends on the underlying filesystem/credentials being writable — this hasn't been broadly exercised against remote stores yet.

### Subcommands

- **`from_images`** — Convert a 2D image stack or a 3D volume file to OME-Zarr.
  Options: `--stack_dir`, `--stack_pattern`, `--vol_file` (exactly one required), `--voxel_size` (repeatable, 1 or 3 values), `--voxel_size_unit`, `--num_levels`, `--chunk_size`. Argument: `OUTPUT_ZARR`.

- **`extract`** — Extract a whole resolution level or a crop from an OME-Zarr pyramid.
  Options: `--corner`, `--size`, `--center`, `--halfsize`, `--level`/`--mip`/`--dataset_path`, `--output`, `--output_format`. Argument: `ZARR_PATH`.

- **`fix_metadata`** — Interactively populate or correct an OME-Zarr dataset's root metadata (backs up existing attributes first). Argument: `ZARR_PATH`.

- **`apply_mask`** — Apply a binary mask to an OME-Zarr volume, resampled to match each resolution level.
  Options: `--volume`, `--mask` (required), `--threshold`, `--output`.

- **`config`** — Manage a `KEY=VALUE` env-var settings file that feeds the top-level `--env-file` option's defaults (`config show|set|reset ENV_FILE ...`). Example: `ome-zarr-tools config set settings.env OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=128`, then `ome-zarr-tools --env-file settings.env from_images ...`.

- **`interactive`** — Open a menu of every other subcommand; selecting one launches a step-by-step wizard for its options, then runs it (or shows the equivalent direct command if cancelled). Add `--tui` for a full-screen interface instead: a menu plus an editable form (review and revise any field before submitting, not strictly one-at-a-time), with live autocomplete on any path field. `--tui` requires an attached interactive terminal; without one, it exits with a clear message rather than the default prompt-based flow.

  There's no button or confirmation dialog in `--tui` — every command screen shares the same footer shortcuts, in the same order: `F5` Run (`Save` for `config`), `F6` Copy, `F7` Copy & exit, `F8` toggle the Command Log, `Esc` back to the menu, `Ctrl+C` cancel. Copy and Copy & exit compute the equivalent direct CLI invocation on demand and place it on the clipboard; it isn't shown as a live preview on screen. Once Run is pressed, a live status indicator tracks the command (a progress bar when the remaining work has a countable total, otherwise an animated sparkline), and the log (hidden by default) captures the same output a direct CLI run would print. A few commands get their own richer screen instead of the plain field form: `fix_metadata`/`migrate` always show a diff of current vs. proposed metadata plus a structured view (directly editable for `fix_metadata`); `inspect` shows a scrollable per-level JSON panel and a structure-summary panel, switchable with `F9` (appended after the shared shortcuts); `config` shows an `ENV_FILE` path field, a click-to-insert view of the registry's configurable variables and their defaults, and a plain-text editor for the file's `KEY=VALUE` lines. If the running `--env-file` (if any) contains an unrecognized `OME_ZARR_TOOLS_*` key, the main menu shows a warning row naming it.

- **`migrate`** — Upgrade an OME-Zarr dataset to a target OME-NGFF specification version (`--target_version`, default `0.5`). Since the specification couples metadata version to Zarr storage format (0.4 → Zarr v2, 0.5+ → Zarr v3), migrating also converts storage as needed.

- **`inspect`** — Report, per resolution level and dataset-wide, shape, dtype, chunk shape, shard shape, on-disk (stored) size, and logical (uncompressed) size. Read-only. Options: `--json` (default: text). On-disk size requires listing the store's chunk keys; against a remote store that allows anonymous object reads but not bucket listing, it's reported as unavailable rather than failing the whole command.

Run `ome-zarr-tools <subcommand> --help` for full option details.

## Development

Source lives under `src/ome_zarr_tools/`, one module per subcommand in `commands/`, with shared helpers in `core/` (error/exit-code conventions, metadata backups) and `io/` (image reading, OME metadata read/validate). Tests live under `tests/{contract,integration,unit}/`.

```bash
pytest tests/ -q
ruff check src tests
mypy src
```
