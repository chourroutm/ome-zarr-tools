# CLI Contract: `--env-file` and `config`

## Top-level option

```
ome-zarr-tools [--env-file PATH] <command> [command options/arguments...]
```

- `--env-file PATH`: optional. `PATH` MUST exist (click `exists=True, dir_okay=False`) or the CLI errors before the subcommand runs (Edge Case: "top-level `--env-file` ... doesn't exist").
- When given, every configurable variable in `PATH` that maps to an option of the invoked `<command>` becomes that option's default for this run only. An explicitly passed flag on the command line always wins (verified: click `default_map` precedence).
- When omitted, behavior is byte-for-byte identical to today (built-in defaults only) — no file is ever read implicitly.
- Applies uniformly whether `<command>` is dispatched directly, via `interactive`'s plain wizard, or via `interactive --tui`.
- A recognized-but-invalid value (wrong type for the target option) surfaces as `<command>`'s own normal `click` usage error (e.g. "Error: Invalid value for '--num_levels': 'abc' is not a valid integer."), naming the option — satisfies FR-009 ("clear error naming the variable and the problem") since the option name in the error already identifies which variable was at fault (traceable 1:1 via the registry).
- A duplicate key within the file: warning printed, last occurrence used (FR-015).
- An unrecognized `OME_ZARR_TOOLS_*` key: non-blocking warning printed, command still runs (FR-016).
- A key not starting with `OME_ZARR_TOOLS_`: silently ignored by this feature (may be a legitimate unrelated variable, e.g. cloud credentials).

**Contract tests**:
- An invalid value for a configured variable (e.g. `OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS=notanumber`) produces a clear, non-crashing `click` usage error when the target command runs with `--env-file` (FR-009).
- An unrecognized `OME_ZARR_TOOLS_*` key in the `--env-file` used for a live command run prints a non-blocking warning and the command still exits 0 (FR-016).
- A duplicate key in the `--env-file` used for a live command run prints a warning and the last occurrence's value is the one actually applied (FR-015).

## `config show ENV_FILE`

- `ENV_FILE`: required positional argument, must exist (error otherwise, Edge Case).
- Prints the file's `KEY=VALUE` contents.
- Duplicate key: warning printed (FR-015), the *displayed* value is the last occurrence's (consistent with what an actual command run would use).
- Unrecognized `OME_ZARR_TOOLS_*` key: printed as an error-level message (FR-016), command still exits 0 and still shows the rest of the file.

**Contract test** (`tests/contract/test_config.py`): `config show` on a file with one recognized and one unrecognized-but-`OME_ZARR_TOOLS_`-prefixed key shows both, flags only the second.

## `config set ENV_FILE KEY=VALUE [KEY=VALUE...]`

- `ENV_FILE`: required positional argument; created if it doesn't exist.
- Each `KEY` MUST be a syntactically valid environment-variable identifier (`^[A-Za-z_][A-Za-z0-9_]*$`) — any invalid key aborts the whole command with a non-zero exit code and writes nothing (FR-005, all-or-nothing).
- A key already present in the file has its value updated in place; a new key is appended (FR-003) — never produces a new duplicate line for an existing key.
- The `KEY`(s) being set are NOT validated against the `ConfigurableVariable` registry (a value can be set for any syntactically valid key, recognized or not — recognition only affects reporting, not write acceptance, so a user can pre-stage a variable for an option added in a future version). The file's pre-write read (of its *existing* content, before merging in the new pairs) still goes through the same duplicate-key (FR-015) and unrecognized-`OME_ZARR_TOOLS_*`-key (FR-016, error-level — this is a `config` subcommand) reporting every other read does, since `set` uses the same shared `read_env_file()`.

**Contract tests**:
- Round-trip: `set` then `show` reflects the value; `set` again on the same key updates rather than duplicating (assert no duplicate-key warning appears on a subsequent `show`).
- Invalid key (`1BAD=x`) exits non-zero and leaves the file untouched (or uncreated).
- `set`-ing a new key into a file whose *existing* content already has an unrecognized `OME_ZARR_TOOLS_*` key reports that pre-existing key as an error-level message (FR-016); a pre-existing duplicate key reports a warning (FR-015) — in both cases the new pair is still written.

## `config reset ENV_FILE [KEY...] [--all]`

- `ENV_FILE`: required positional argument; MUST exist (error otherwise, Edge Case) — nothing to reset in a file that was never created.
- With one or more `KEY` arguments: removes each from the file (silently no-op for a key not present — matches prior JSON-based `reset`'s behavior).
- With `--all`: deletes the file entirely, ignoring any `KEY` arguments.
- Exactly one of "one or more keys" or `--all` is required (mirrors the prior command's own validation shape) — both/neither is a usage error.

**Contract test**: `set` two keys, `reset` one by name, `show` reflects only the other remaining; `reset --all` on the resulting file removes it entirely (subsequent `show` errors, per the "file doesn't exist" edge case).

## Renamed/removed options (prerequisite to the variable registry)

| Command | Before | After | FR |
|---|---|---|---|
| `apply_mask` | `--temporary_upsample` (flag) | *(removed)* | FR-013 |
| `inspect` | `--format`/`output_format` (`Choice(["text","json"])`, default `text`) | `--json` (flag, `as_json` dest, default `False`) | FR-012 |
| `from_images` | `--num_downsampling` | `--num_levels` | FR-011 |

**Contract tests** (existing files, modified):
- `tests/contract/test_apply_mask.py`: invoking with `--temporary_upsample` now exits non-zero ("no such option").
- `tests/contract/test_inspect.py`: `--help` lists `--json`, not `--format`; `--json` produces the same output `--format json` used to.
- `tests/contract/test_from_images.py`: `--help` lists `--num_levels`, not `--num_downsampling`; behavior unchanged under the new name.
