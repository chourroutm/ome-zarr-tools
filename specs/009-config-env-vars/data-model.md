# Phase 1 Data Model: Config Command Uses Env-Var Files

## Entities

### `EnvFile` (conceptual — a plain file on disk, not a class)

A text file at a user-named path, containing zero or more lines of the form `KEY=VALUE`, optional blank lines, and optional `#`-prefixed comment lines. There is no fixed/default path anywhere in this feature (spec Assumptions: "No implicit file locations").

**Parsed representation**: `dict[str, str]` — raw string values only; type conversion into an option's real type (int, float, bool, Choice) is deferred entirely to `click`'s own `ParamType.convert()`, invoked when the value flows through `Context.default_map` (research.md §3) — this feature never hand-converts a value itself except to detect FR-009's "invalid value" case, which click already surfaces as its own `UsageError` when `.main()` runs.

**Parsing rules** (`core/env_file.py::read_env_file`):
- Skip blank lines (whitespace-only).
- Skip lines whose first non-whitespace character is `#`.
- Split each remaining line on the first `=`; no `=` present → raise `CliError` naming the file path and 1-indexed line number (FR edge case).
- Key syntax is *not* validated on read (only on `config set`, FR-005) — a file can contain any string as a key; only recognized-variable matching (below) cares whether it looks like `OME_ZARR_TOOLS_*`.
- If a key appears on more than one line, the last occurrence's value wins; `read_env_file` prints a warning (`click.echo(..., err=True)`) naming the duplicated key, every call, per FR-015.

**Write model** (`core/env_file.py::write_env_file`): given a `dict[str, str]`, writes one `KEY=VALUE` line per entry (insertion order), no comments/blank lines preserved from a prior version of the file (an edit-and-rewrite model, not an in-place line patch) — consistent with FR-003's "update in place" being about the *logical* key/value set, not literal on-disk byte preservation of comments a user may have added. (If a future need for comment-preserving edits arises, that's a new feature; not required by any FR here.)

### `ConfigurableVariable` (new, `core/config_registry.py`)

```python
@dataclass(frozen=True)
class ConfigurableVariable:
    name: str                                  # e.g. "OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE"
    targets: tuple[tuple[str, str], ...]        # ((command_name, option_dest_name), ...) -- 1 entry normally, 2 for a shared variable
```

A module-level `CONFIGURABLE_VARIABLES: list[ConfigurableVariable]` is the single source of truth, built by hand (research.md §5), matching the spec's own table with FR-013/FR-014 resolved (13 entries — the `apply_mask` no-op row removed per FR-013; `from_images --chunk_size` stays unscoped per FR-014):

| `name` | `targets` |
|---|---|
| `OME_ZARR_TOOLS_FROM_IMAGES_VOXEL_SIZE_UNIT` | `[("from_images", "voxel_size_unit")]` |
| `OME_ZARR_TOOLS_FROM_IMAGES_NUM_LEVELS` | `[("from_images", "num_levels")]` (post FR-011 rename) |
| `OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE` | `[("from_images", "chunk_size")]` |
| `OME_ZARR_TOOLS_TARGET_VERSION` | `[("from_images", "target_version"), ("migrate", "target_version")]` |
| `OME_ZARR_TOOLS_CHUNKS_PER_SHARD` | `[("from_images", "chunks_per_shard"), ("migrate", "chunks_per_shard")]` |
| `OME_ZARR_TOOLS_EXTRACT_LEVEL` | `[("extract", "level")]` |
| `OME_ZARR_TOOLS_EXTRACT_OUTPUT_FORMAT` | `[("extract", "output_format")]` |
| `OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD` | `[("apply_mask", "threshold")]` |
| `OME_ZARR_TOOLS_INSPECT_JSON` | `[("inspect", "as_json")]` (post FR-012 rename; dest name `as_json`, not `json` — `inspect.py` imports the `json` module, so the click parameter must not be named `json` or it would shadow that import inside `inspect()`'s body) |
| `OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS` | `[("downsample", "num_levels")]` |
| `OME_ZARR_TOOLS_DOWNSAMPLE_LABEL` | `[("downsample", "label")]` |
| `OME_ZARR_TOOLS_UPSAMPLE_NUM_LEVELS` | `[("upsample", "num_levels")]` |
| `OME_ZARR_TOOLS_UPSAMPLE_SMOOTH` | `[("upsample", "smooth")]` |

**Lookup helpers**:
- `build_default_map(values: dict[str, str]) -> dict[str, dict[str, str]]`: for each `(name, raw_value)` in `values`, if `name` matches a `ConfigurableVariable`, add `raw_value` under every `(command, option)` target; returns the nested-by-command shape `research.md §3` needs. Values stay raw strings — `click` converts them.
- `unrecognized_keys(values: dict[str, str]) -> list[str]`: every key in `values` that starts with `OME_ZARR_TOOLS_` and does not match any `ConfigurableVariable.name`. Keys that don't start with that prefix are never included (FR-016/SC-006 — a file may hold unrelated variables).

### `EnvFileParseWarning` / reporting (no new class — plain strings + severity routed by caller)

`read_env_file` returns `(values, duplicate_warnings: list[str])`; `unrecognized_keys()` returns `list[str]`. Each of the three call sites (data flows below) decides how to present these:

| Caller | Duplicate-key warning | Unrecognized-key report |
|---|---|---|
| `config show` / `set` / `reset` | printed as a warning | printed as an **error-level** message (FR-016), command still completes |
| Top-level `--env-file` on a live command run | printed as a warning | printed as a **non-blocking warning** (FR-016), command still runs |
| TUI `CommandMenuScreen` | shown in the below-menu warning row | shown in the same below-menu warning row (FR-016) |

## State / Control Flow

```
ome-zarr-tools --env-file FILE <command> [flags...]
                      │
                      ▼
     cli() group callback (cli.py)
     ├─ read_env_file(FILE) -> (values, dup_warnings)   [print dup_warnings]
     ├─ unrecognized_keys(values) -> names               [print as warning]
     ├─ build_default_map(values) -> mapping
     └─ ctx.default_map = mapping   (nested by command name)
                      │
                      ▼
          <command>'s own click dispatch
          (explicit flags > default_map values > built-in defaults)
```

```
interactive [--tui]                          (also reachable via --env-file FILE interactive ...)
     │
     ▼
interactive() reads ctx.parent.default_map (already built above, if --env-file was given)
     │
     ├─ plain wizard: _confirm_and_run(command, tokens) passes
     │     default_map=mapping.get(command.name, {}) to command.main(...)
     │
     └─ --tui: InteractiveTUIApp holds `mapping`; CommandMenuScreen shows a warning row
           if unrecognized_keys(...) is non-empty; when a command is Run,
           tui/execution.py::run_command(..., default_map=mapping.get(command.name, {}))
```

```
ome-zarr-tools config show|set|reset ENV_FILE ...
     │
     ▼
read_env_file(ENV_FILE) -> (values, dup_warnings)   [print dup_warnings]
unrecognized_keys(values) -> names                   [print as error-level message]
<show: print values> | <set: merge + write_env_file> | <reset: remove keys / delete file>
```

## Validation Rules (from Functional Requirements)

- `config set`: every `KEY` in every pair MUST match `^[A-Za-z_][A-Za-z0-9_]*$` (FR-005); on any invalid key, no write occurs at all (all-or-nothing).
- `config set`/`reset`: file path handling per FR-003/FR-004 (`set` creates if missing; `reset`/`show` error if missing, FR edge cases).
- Env-file line syntax: `KEY=VALUE`, optional blank/`#`-comment lines; anything else is a parse error naming file + line.
- Duplicate key in one file: last occurrence wins + warning, every read (FR-015).
- Unrecognized key: only `OME_ZARR_TOOLS_*`-prefixed unknowns are flagged; severity varies by caller (FR-016).
- Explicit CLI flag always overrides a `--env-file`-supplied default (FR-007) — guaranteed by `click`'s own `default_map` precedence, verified empirically (research.md §3), not by any bespoke code in this feature.
