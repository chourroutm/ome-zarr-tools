# Phase 0 Research: Rebuild OME-Zarr Tools CLI Package

Source material: `README.md`, current `ome_zarr_tools/*.py` and `cli.py`, and the project's closed GitHub issues (`chourroutm/ome-zarr-tools`, `state:closed`, #2–#8), per the user's explicit request to use those issues as the suggested-argument baseline and to confirm before deviating.

## Closed-issue argument baseline vs. current code

| Issue | Command | Issue's suggested args | Current code | Decision |
|---|---|---|---|---|
| #8 | `from_images` | `--stack_dir`, `--stack_files`, `--stack_pattern`, `--vol_file` | `--stack_dir`, `--stack_pattern`, `--vol_file`, `--voxel_size`, `--voxel_size_unit`, `--num_downsampling`, `--chunk_size` | **User-confirmed**: keep current code's 3 input options (no `--stack_files`); keep `--num_downsampling`/`--chunk_size` since the OME-Zarr writer needs them. |
| #7 | `extract` | `--corner`, `--size`, `--center`, `--halfsize`, `--mag`, `--mip`/`--level`/`--dataset_path`, `--scale`, `--output`, `--output_format` | Matches issue exactly | No deviation — adopt as-is. |
| #6 | `fix_metadata` (issue names it with alias `fix_zattrs`) | interactive session, no explicit flags | `fix_metadata`, no alias | **User-confirmed**: `fix_metadata` only, no `fix_zattrs` alias. |
| #5 | `apply_mask` | `--volume`, `--mask`, `--threshold` (default 0.5), `--temporary_upsample` | Matches issue exactly | No deviation — adopt as-is. |
| #4 | `from_jp2k` (closed: Not Planned) | `--stack_dir`, `--stack_glob`; dependency: JP2K reader | Superseded — no dedicated command | No deviation — issue itself says superseded by `from_images` (#8). |
| #3 | `config` | `--user`, `--project`, `--set key=value` | `show`/`set`/`reset` subcommands with `--user`/`--project` | Current code's `show`/`reset` subcommands are additive, not conflicting with the issue's arguments — adopt as-is. |
| #2 | `from_tiff` (closed: Not Planned) | `--stack_dir`, `--stack_glob`, `--vol_file`; dependency: `tifffile` | Superseded — no dedicated command | **User-confirmed**: do not add `tifffile` as an explicit dependency; `imageio` (which delegates to `tifffile`/`pillow` internally per format) is sufficient, consistent with the issue being closed as Not Planned. |

`interactive`, `migrate`, and `inspect` have no corresponding closed issue — they are net-new per this feature's spec, so no baseline-vs-deviation question applies to them.

## Other technical decisions

- **Decision**: Depend on `zarr` ≥3 rather than pinning to the 2.x series.
  **Rationale**: `migrate`'s Zarr v2 → v3 storage conversion (FR-015) requires a `zarr` release that can read v2 and write v3 stores natively.
  **Alternatives considered**: Shelling out to a separate conversion tool — rejected, adds a non-Python dependency for something the primary library already does.

- **Decision**: Promote `ome-zarr-models` from an optional, best-effort dependency (today's `try/except ImportError`) to a required one.
  **Rationale**: `fix_metadata` already uses it for validation, and `migrate` needs the same validation to confirm a dataset matches its target spec version (FR-012); making it optional would let `migrate` silently skip the one check that proves the migration worked.
  **Alternatives considered**: Keep it optional and skip validation when absent — rejected, undermines FR-005's "recoverable, validated write" guarantee for the one command whose whole job is spec-version correctness.

- **Decision**: Drop the direct `pims` import (`from pims.api import UnknownFormatError`) from `from_images`; catch `ImportError` around the `dask.array.image` fast path and fall back to `imageio` for anything else.
  **Rationale**: `pims` is an internal dependency of `dask.array.image`, not something this package calls directly; importing it just to catch one of its exception types is fragile across `dask`/`pims` version combinations.
  **Alternatives considered**: Keep the explicit `pims` import and pin its version — rejected as unnecessary surface area for a dependency this package never calls directly.

- **Decision**: Implement `interactive`'s menu and per-command wizards with `click` alone (`click.prompt`, `click.confirm`, `click.Choice`) rather than adding a TUI/prompt library (e.g., `questionary`, `InquirerPy`).
  **Rationale**: Keeps the "agreed-upon set of dependencies" minimal; `click` is already the CLI framework and its prompt primitives are enough to present a numbered menu and collect each subcommand's options.
  **Alternatives considered**: `questionary` for arrow-key menus — nicer UX but a new dependency for a capability `click` already covers adequately; can be revisited later if plain prompts prove too clunky.

- **Decision**: `migrate` treats "OME metadata version" and "Zarr storage format" as two independent axes it can act on in one invocation (per FR-015), detecting each separately and only touching what's out of date.
  **Rationale**: A dataset can be OME-Zarr-0.4-metadata-on-Zarr-v2, 0.4-on-v3, or already fully current; forcing both migrations together would do unnecessary/unwanted work on datasets that only need one.
  **Alternatives considered**: Two separate commands (`migrate-metadata`, `migrate-storage`) — rejected, spec (FR-003) calls for one `migrate` command and splitting adds a second thing for `interactive`'s menu to explain.

- **Decision**: Move packaging fully into `pyproject.toml` (PEP 621) and delete `setup.py`.
  **Rationale**: The two files currently disagree (`setup.py` hardcodes `install_requires=["click"]` and a static version; `pyproject.toml` declares a dynamic version and no dependencies at all) — a single source of truth is required for FR-009's reproducible-install guarantee.
  **Alternatives considered**: Keep both in sync manually — rejected, that's exactly the drift that exists today.

- **Decision**: Adopt a `src/` layout (`src/ome_zarr_tools/...`) instead of the current root-level `ome_zarr_tools/` + root `cli.py`.
  **Rationale**: Prevents accidentally importing the package from the working directory instead of the installed one during tests — a common source of "works here, fails in CI" bugs — and is the layout most current Python packaging guides recommend.
  **Alternatives considered**: Keep flat layout — rejected as the flat layout is what let `cli.py` and the package drift apart from `pyproject.toml` in the first place.

- **Decision**: Lint/format with `ruff` and type-check with `mypy` as dev-only dependencies; no change to runtime dependencies.
  **Rationale**: Both are single fast tools covering what previously would have needed several (flake8 + isort + black); neither is imported by the shipped package.
  **Alternatives considered**: `flake8` + `black` + `isort` — rejected as three tools doing what one (`ruff`) now does.

## `bioio` / `bioio-ome-zarr` / `ngff-zarr` — issue-tracker review

Per the user's request to weigh using [bioio-devs/bioio](https://github.com/bioio-devs/bioio) and [fideus-labs/ngff-zarr](https://github.com/fideus-labs/ngff-zarr) unless they carry stale, unresolved bugs. Checked each repo's open issues (via the public GitHub API) as of 2026-08-05.

| Repo | Finding | Stale? | Verdict |
|---|---|---|---|
| `bioio-devs/bioio` | #144: TIFF/PNG reads 2–8× slower than native readers, possible double-reads. Opened 2025-07-04, no update since 2025-09-17 (~11 months). | Yes | **Do not adopt** for `from_images`'s core read path — the tool's whole point is handling large datasets efficiently. |
| `bioio-devs/bioio-ome-zarr` | Only open items are feature requests (HCS, labels, translations, OZX archives), several stale (Dec 2025, no traction), but no correctness bugs against what we'd use (`OmeZarrWriter`). | N/A (no bugs) | **Keep using it** for `from_images`'s pyramid writer, as already planned. |
| `fideus-labs/ngff-zarr` | #135: `to_multiscales()` rounding bug — generates too few pyramid levels when chunk size exactly divides image size. Opened 2025-02-07, no update since 2025-06-17 (~14 months). | Yes | **Do not adopt** `to_multiscales()` for pyramid generation — keep `bioio-ome-zarr`'s writer for that in `from_images`. |
| `fideus-labs/ngff-zarr` | #628: `tensorstore` write backend doesn't declare codecs, silently halves chunk size on round-trip. Opened 2026-08-04 (day before this research), fix already in draft PR. | No — fresh, actively being fixed, and only affects the *opt-in* `use_tensorstore=True` path (default backend is plain `zarr-python`). | **Not a blocker**: use `ngff-zarr`'s default `zarr-python` backend, never pass `use_tensorstore=True`. |
| `fideus-labs/ngff-zarr` | `to_ngff_zarr(store, multiscales, version=...)` reads OME-Zarr v0.1–0.6 and writes v0.4–0.6, i.e. exactly the spec-version conversion `migrate` needs, on a code path untouched by the `to_multiscales()`/`tensorstore` bugs above. | — | **Adopt** as the engine behind `migrate`. |

**Decision**: `migrate` is implemented on top of `ngff-zarr.from_ngff_zarr()`/`to_ngff_zarr(..., version=target)` (default backend), rather than hand-written OME-NGFF schema translation as originally sketched. `from_images` keeps `imageio`/`dask.array.image` for reading and `bioio-ome-zarr`'s `OmeZarrWriter` for writing — unchanged from the earlier decision in this document, now with issue-tracker evidence backing it.

**Follow-on spec correction**: while reading `ngff-zarr`'s docs to confirm the above, its version/backend semantics revealed that OME-NGFF specification version and Zarr storage format are **not independent** — v0.4 is defined on Zarr v2, v0.5+ on Zarr v3, so a dataset can't (validly) target one axis without the other. This contradicted FR-015 as originally written (which modeled them as independently selectable) and the `--target_storage_format`/`--metadata_only`/`--storage_only` options in `contracts/cli-contract.md`. **Confirmed with the user**: `migrate` was redesigned around a single `--target_version` option; `spec.md` (FR-003, FR-015, FR-012, User Story 3, Migration Record, SC-003) and `contracts/cli-contract.md` were updated accordingly.

## `inspect` (folded in after `/speckit-tasks`)

- **Decision**: Compute chunk shape, shard shape, and stored (on-disk) byte counts via `zarr`'s own array/store introspection (`zarr.Array` metadata plus its stored-size accounting, e.g. iterating `array.nchunks`/store keys to sum sizes, or the array's own reported nbytes-stored where the installed `zarr` version exposes it) rather than a hand-rolled filesystem walk.
  **Rationale**: `zarr` (already a required dependency, ≥3) is the one component that already knows how to enumerate an array's chunk/shard keys correctly for both Zarr v2 and v3 layouts, including sharded arrays — reimplementing that by walking the filesystem directly would have to special-case both formats and would break the moment the store isn't a plain local directory (`cloudpathlib`-backed remotes).
  **Alternatives considered**: `os.walk`/`pathlib.rglob` + manual size summation — rejected as format- and store-specific, and blind to Zarr v3 sharding (a shard file holds multiple logical chunks, so naive per-chunk-file counting is wrong for sharded arrays).

- **Decision**: `inspect` supports a human-readable table (default) and a `--format json` mode; no third format.
  **Rationale**: Matches FR-019 minimally — text for humans, JSON for scripts (consistent with the tool's other scripting-friendly conventions, e.g. exit codes).
  **Alternatives considered**: CSV/YAML output — rejected as unnecessary; JSON already covers the "pipe into another tool" use case.

- **Decision**: `inspect` is purely additive — it introduces no new required dependency and touches no other command's code.

## Implementation-time API verification (during `/speckit-implement`)

Installed the real dependency versions (`zarr==3.3.0`, `ngff-zarr==0.41.0`, `ome-zarr-models==1.7`, `bioio-ome-zarr` current) and checked actual APIs against what the doc-summary research above assumed:

- **`bioio_ome_zarr.OMEZarrWriter`** (note capitalization — not `OmeZarrWriter` as the pre-rebuild code imported) takes precomputed `level_shapes` and a `chunk_shape`/`shard_shape`, then `.initialize()` + `.write_full_volume(dask_array)` — there is no automatic "give me N downsampling levels" constructor arg like the pre-rebuild code assumed. `from_images` computes `level_shapes` itself (halving spatial dims per level, floor-bounded at 1) before constructing the writer.
- **Dataset path convention differs by writer**: `bioio_ome_zarr.OMEZarrWriter` writes dataset paths `"0"`, `"1"`, … (matches the pre-rebuild code's assumption), but `ngff_zarr.to_ngff_zarr()` (used by `migrate`) writes `"scale0/<image_name>"`, `"scale1/<image_name>"`, …. **Correction**: `extract`'s `--level` must resolve to `datasets[level].path` from the group's own `multiscales` metadata (then `group[path]`, which supports slash-separated nested paths directly) rather than assuming the level number is itself a literal store key. Updated in `contracts/cli-contract.md`.
- **`ome_zarr_models.open_ome_zarr(group, version=None)`** auto-detects 0.4 vs 0.5 and returns a validated model (raises on invalid metadata) with an `.ome_zarr_version` attribute — this is the single call `io/ome_metadata.py` uses for both "does this validate" and "what version is it", replacing the plan's separate detect/validate calls with one.
- **`zarr.Array` exposes what `inspect` needs directly**: `.shape`, `.dtype`, `.chunks`, `.shards` (`None` when unsharded), `.nbytes` (logical), and `.nbytes_stored()` (a plain callable returning `int`, not the fragile private-field `ArrayInfo` dataclass) — simpler than originally planned.
- **`ngff_zarr.to_ngff_zarr(store, multiscales, version=..., use_tensorstore=False, ...)`** and **`from_ngff_zarr(store, validate=False, version=None)`** signatures match what `migrate.py` was designed around; no changes needed there.

**Output**: All `NEEDS CLARIFICATION` items from the Technical Context are resolved above; no open unknowns remain.
