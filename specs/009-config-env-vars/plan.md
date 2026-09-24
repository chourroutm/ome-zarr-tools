# Implementation Plan: Config Command Uses Env-Var Files

**Branch**: `009-config-env-vars` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-config-env-vars/spec.md`

## Summary

Replace `config`'s JSON-file-based, dead-end settings (written and read back, but never consulted by any command) with a plain `KEY=VALUE` env-file that actually feeds command defaults. `ome-zarr-tools` gains a top-level `--env-file PATH` option; its values become `click` `default_map` entries for whichever subcommand runs (including runs launched from the `interactive` wizard and the TUI), so an explicit flag always still wins. `config show|set|reset` operate on a file named by a required positional `ENV_FILE` argument (no more `--user`/`--project` scope, no `--env-file` flag on `config` itself, to avoid colliding with the distinct top-level option). A small, explicit static registry — not automatic introspection, which is exactly what caused today's silent `extract`/`inspect` `output_format` collision in `collect_default_values()` — maps each configurable variable name to the one or two `(command, option)` pairs it feeds.

Two decisions the spec deliberately deferred to this phase (FR-013, FR-014) are resolved here:
- **FR-013 → remove**: `apply_mask --temporary_upsample` is dead code with no defined "real" behavior to wire up (mask resampling already always happens automatically); Principle I requires removing dead code, not leaving it "for later." It is deleted from `apply_mask.py` and from the configurable-variable registry.
- **FR-014 → do not add**: giving `migrate` a rechunking capability is a genuine new behavior (touching `apply_migration`/`_convert_and_validate`, interacting with `--chunks_per_shard`) unrelated to config plumbing — out of scope per Principle I's "avoid refactoring unrelated code while adding a feature." `from_images --chunk_size` stays scoped exactly as originally proposed, not merged.

## Technical Context

**Language/Version**: Python 3.12 (existing project)

**Primary Dependencies**: `click` (CLI/option framework, incl. `Context.default_map`), `textual` (TUI, existing), no new third-party dependency

**Storage**: Plain-text `KEY=VALUE` files at a user-named path (no fixed location) — replaces the current JSON config file

**Testing**: `pytest` (`tests/unit`, `tests/contract`, `tests/integration`), matching existing conventions

**Target Platform**: Same CLI/TUI tool, unchanged (Linux/macOS dev + HPC)

**Project Type**: Single project (existing `src/ome_zarr_tools` package + `tests/`)

**Performance Goals**: N/A (trivial file I/O, no measurable performance target)

**Constraints**: Must not regress any currently-passing command's default behavior when `--env-file` is omitted (`FR-007`); must not silently apply defaults to a command whose option the user explicitly set (`FR-007`, verified empirically — see research.md)

**Scale/Scope**: One CLI command family (`config`), one new top-level option (`--env-file`), ~13 configurable variables across 7 existing commands, one TUI screen rewrite (`config_screen.py`) and one TUI screen addition (a warning row on `CommandMenuScreen`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Code Quality)**: The old JSON config path (`read_config`/`write_config`/`target_config_path`/`USER_CONFIG_REL`/`PROJECT_CONFIG_NAME`/`_parse_kv_pair`) becomes fully unused once replaced and MUST be deleted, not kept alongside the new code. `apply_mask --temporary_upsample` (confirmed dead, FR-013) MUST be deleted rather than exposed as configurable dead weight. **PASS** (plan deletes both).
- **Principle II (Test-First, NON-NEGOTIABLE)**: Every FR below maps to at least one contract/integration test (see contracts/ and quickstart.md); the `--temporary_upsample` removal gets its own regression test (option now rejected). **PASS**, enforced at `/speckit-tasks`/`/speckit-implement` time.
- **Principle III (Deliberate Commits)**: Unaffected by planning; commits still only made when the user asks. **PASS**.
- **Quality Gates**: The TUI's config screen and menu screen are both touched — per the Gates section, both MUST be exercised via a headless Textual test covering the golden path (edit + save an env-file) and one edge case (unrecognized-key warning shown). Planned for in contracts/tui-contract.md.

No violations requiring the Complexity Tracking table.

### Post-Design Re-Check (after Phase 1)

- Two new modules (`core/env_file.py`, `core/config_registry.py`) are small, single-purpose, and mirror an existing pattern in this codebase (`core/zarr_path.py`, `core/click_ext.py`) rather than introducing a new kind of abstraction — still **PASS** on Principle I's "prefer editing existing modules over adding new abstractions" (a new module is justified here the same way `click_ext.py` was: cross-cutting CLI infrastructure used by multiple commands, not command-specific logic that belongs in one `commands/*.py` file).
- No new third-party dependency was introduced (`click.Context.default_map` is a built-in mechanism, verified empirically in research.md) — nothing new for Principle I's "unused dependencies" concern to flag.
- data-model.md's validation rules and contracts/*.md's per-endpoint behaviors each cite the FR they satisfy, and each contract lists its own test(s) — Principle II's per-behavior-change test requirement is traceable, not just asserted.
- No design decision here conflicts with a constitution principle without justification already given inline (FR-013/FR-014 resolutions are justified against Principle I directly in research.md §1-2). **Overall: PASS, no Complexity Tracking entries needed.**

## Project Structure

### Documentation (this feature)

```text
specs/009-config-env-vars/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   ├── cli-contract.md
│   └── tui-contract.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/ome_zarr_tools/
├── cli.py                          # MODIFIED: top-level --env-file option, ctx.default_map wiring
├── core/
│   └── env_file.py                 # NEW: read_env_file/write_env_file/is_valid_env_key, parsing
├── core/
│   └── config_registry.py          # NEW: static ConfigurableVariable list + lookup helpers
├── commands/
│   ├── config.py                   # REWRITTEN: show/set/reset over ENV_FILE positional arg
│   ├── apply_mask.py                # MODIFIED: --temporary_upsample removed (FR-013)
│   ├── inspect.py                   # MODIFIED: --format/output_format -> --json flag (FR-012)
│   ├── from_images.py               # MODIFIED: --num_downsampling -> --num_levels (FR-011)
│   └── interactive.py               # MODIFIED: threads default_map through wizard + TUI runs
├── tui/
│   ├── app.py                       # MODIFIED: CommandMenuScreen shows unrecognized-key warning
│   ├── execution.py                 # MODIFIED: run_command accepts default_map
│   └── screens/
│       └── config_screen.py         # REWRITTEN: ENV_FILE PathField, plain-text editor, corrected registry-driven defaults list

tests/
├── unit/
│   ├── test_env_file.py             # NEW
│   └── test_config_registry.py      # NEW
├── contract/
│   ├── test_config.py               # REWRITTEN
│   ├── test_apply_mask.py           # MODIFIED (temporary_upsample removal regression)
│   ├── test_inspect.py              # MODIFIED (--json rename)
│   └── test_from_images.py          # MODIFIED (--num_levels rename)
└── integration/
    ├── test_config.py               # REWRITTEN
    ├── test_cli_env_file_defaults.py # NEW (end-to-end: env-file -> command default -> explicit override)
    ├── test_interactive.py          # MODIFIED (default_map threading)
    └── test_tui_screens.py          # MODIFIED (config screen rewrite, menu warning)
```

**Structure Decision**: Single project, existing layout. Two new small `core/` modules (env-file I/O, variable registry) keep the new parsing/lookup logic testable in isolation (`tests/unit`) and out of `commands/config.py`, mirroring the existing `core/zarr_path.py`/`core/click_ext.py` pattern already used in this codebase for cross-cutting CLI infrastructure.

## Complexity Tracking

*No violations — table not needed.*
