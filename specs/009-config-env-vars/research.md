# Phase 0 Research: Config Command Uses Env-Var Files

## 1. Deferred spec decision — FR-013: fix or remove `apply_mask --temporary_upsample`?

**Decision**: Remove the flag entirely from `apply_mask.py`; do not add it to the configurable-variable registry.

**Rationale**: Its own current help text ("Reserved for CLI compatibility; mask resampling is always applied automatically") confirms mask resampling already happens unconditionally — there's no dormant "temporary vs. permanent upsample" distinction anywhere in `apply_mask.py`'s body to wire up; the parameter is accepted into the function signature and never read again. No design document, commit message, or test in this repository indicates what alternate behavior "temporary" was ever meant to select. Inventing new behavior for it would be speculative (Principle I: "do not introduce speculative configuration... for scenarios that do not currently exist"), and Principle I separately requires removing confirmed dead code rather than leaving it "for later." Grep confirms zero test references to `--temporary_upsample`, so removal has no test fallout beyond adding the regression test that proves it.

**Alternatives considered**: Wiring it to a real "upsample the mask in memory only vs. write a persisted upsampled copy" distinction was considered, but `apply_mask` never persists an upsampled mask copy today (it computes `nearest_upsample`/`label_downsample` lazily via dask each run) — there is no non-"temporary" behavior to contrast it against, so this would be a new feature, not a fix, and out of scope for a config-plumbing change.

## 2. Deferred spec decision — FR-014: should `migrate` gain `--chunk_size`?

**Decision**: No. `migrate` is not given a `--chunk_size` option. `from_images --chunk_size` remains scoped as `OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE`, not merged with anything.

**Rationale**: `migrate` currently has no rechunking capability at all (confirmed: `apply_migration`/`_convert_and_validate` never call `.rechunk()`; only `--chunks_per_shard`, a sharding-factor concern, exists). Adding one would require new behavior in `commands/migrate.py` (thread a chunk size through the conversion path, decide its interaction with `--chunks_per_shard` and with a source array's existing chunk shape) — a real, separately-testable feature, not a side effect of switching `config`'s storage format. Principle I ("prefer minimal, targeted diffs; avoid refactoring unrelated code while ... adding a feature") rules this out for the current feature's scope.

**Alternatives considered**: Adding `--chunk_size` now, merged with `from_images`'s, was the spec's other named possibility — rejected because it would mean shipping a new, un-speced, untested rechunking behavior on `migrate` bundled inside a config-plumbing PR.

## 3. Mechanism: how does `--env-file` actually change a command's default?

**Decision**: Use `click.Context.default_map`, which click already supports for exactly this purpose (it's the same mechanism `click`'s own docs recommend for config-file-driven defaults).

**Verified empirically** (see below) two call shapes are both needed, because this codebase invokes commands two different ways:

- **Direct dispatch** (`ome-zarr-tools --env-file X downsample ...`): the top-level group's callback sets `ctx.default_map = {"downsample": {"num_levels": "5"}, ...}` — nested one level by subcommand name, exactly what a `click.Group`'s own subcommand-context construction expects.
- **Ad-hoc dispatch** (`interactive`'s wizard, and the TUI's `run_command`, both call `some_command.main(args=tokens, ...)` directly on a leaf `click.Command`, bypassing the group's context tree entirely): the *same* per-command dict must be passed *flat*, as `default_map={"num_levels": "5"}`, directly to that call's own `default_map=` kwarg.

Confirmed with a minimal script: both shapes correctly (a) apply the string value through the option's own `type` conversion (`'5'` → `int` `5`, no manual coercion needed anywhere in this feature) and (b) are overridden by an explicit `--num_levels 2` on the command line. This satisfies FR-007's "use the env-file's value as default; explicit flag always wins" for free, using click's own precedence rules — no bespoke override-detection code needed.

**Implication for `interactive`/TUI**: build one shared `build_default_map(env_file) -> dict[str, dict[str, object]]` (nested by command name), reused in two places: `cli.py`'s group callback assigns it to `ctx.default_map` directly; `interactive.py`/`tui/execution.py` instead look up `mapping.get(command.name, {})` and pass that flat sub-dict as `default_map=` to their own direct `.main()` calls. This also means the top-level `--env-file` must be threaded from the group's context down into `interactive` (which already takes `@click.pass_context`, so `ctx.parent.default_map` — or better, a dedicated `ctx.obj` set by the group holding the parsed mapping — is reachable) and into the TUI app object, which forwards it to `tui/execution.py::run_command`'s new `default_map` parameter for whatever command the user actually runs from the menu.

**Alternatives considered**: Manually reading `os.environ`-style overrides inside every command body was rejected — `default_map` is click's own built-in, well-tested mechanism for exactly this, requires no per-command code changes, and composes correctly with `envvar=`-based options if any are added later.

## 4. Env-file parsing: format details not pinned down by any FR

**Decision**: Standard dotenv conventions: one `KEY=VALUE` pair per non-blank, non-comment line; blank lines are skipped; lines starting with `#` (after stripping leading whitespace) are skipped as comments; anything else that doesn't split on the first `=` into `KEY` and `VALUE` is a malformed-line error naming the file and line number (FR edge case).

**Rationale**: The spec's own Assumptions section already frames this as "the widely recognized convention for this kind of file" and explicitly compares it to `set -a; source <file>; set +a` — real dotenv/shell-sourced files universally support blank lines and `#` comments, and rejecting them outright would make the file useless for the kind of hand-editing (and reuse alongside unrelated exports like cloud credentials, per FR-016/SC-006) the spec anticipates. This is filling in an unspecified-but-uncontroversial detail of an already-decided format, not introducing new scope.

**Alternatives considered**: Rejecting comments (require every non-blank line to be `KEY=VALUE`) would contradict "widely recognized convention" and make hand-editing (explicitly anticipated by the Edge Cases table) needlessly hostile.

## 5. Registry design: explicit static table vs. automatic introspection

**Decision**: A small, explicit, hand-maintained list of `(variable_name, [(command_name, option_dest_name), ...])` entries in a new `core/config_registry.py` — not automatic discovery from `command.params` (which is exactly what today's `collect_default_values()` does, and exactly what produced the undetected `extract`/`inspect` `output_format` collision this feature exists partly to fix).

**Rationale**: FR-006's shared-vs-scoped distinction (`target_version`/`chunks_per_shard` shared; `num_levels` deliberately not) cannot be derived mechanically from option names or types alone — it requires knowing what an option *means*, which only a human decision (already made in the spec) can supply. An explicit table also means a newly-added command option is never silently exposed as configurable (and never silently collides with another) until someone deliberately adds it here, which is the safer default for a tool that already got bitten once by implicit, name-based matching.

**Alternatives considered**: Auto-deriving `OME_ZARR_TOOLS_<COMMAND>_<OPTION>` for every eligible option and only special-casing the two shared exceptions was considered simpler, but still requires an explicit exclusion list for FR-008/FR-009-type exclusions (required options, paths, per-invocation geometry) — at that point the fully-explicit table is barely more code and is strictly safer/more auditable.

## 6. Where duplicate-key and unrecognized-key detection live

**Decision**: `core/env_file.py::read_env_file()` is the single parser used by every call site (`config show`/`set`/`reset`, and the top-level `--env-file` application) and is where duplicate-key detection (last-line-wins + warning, FR-015) happens, since it's the one place that sees every line of the file. Unrecognized-`OME_ZARR_TOOLS_`-key detection (FR-016) is a separate step in `core/config_registry.py` (comparing `read_env_file()`'s parsed keys against the registry), because *how* it's reported (error-level vs. warning-level vs. TUI banner) differs by caller — the registry-lookup function returns a plain list of unrecognized keys and lets each of the three call sites format/route it appropriately, rather than baking one presentation into the shared parser.

**Rationale**: Keeps the low-level parser (`env_file.py`) free of any knowledge of "which variables are known" or "how severe is this," so it stays trivially unit-testable in isolation; keeps severity/routing decisions (FR-016) next to the three places that actually differ (`config` subcommands print an error-styled, non-aborting message; a live command run prints a non-blocking warning; the TUI menu screen renders a warning row).
