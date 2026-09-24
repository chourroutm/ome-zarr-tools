# Feature Specification: Config Command Uses Env-Var Files

**Feature Branch**: `009-config-env-vars`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "change the config command to instead edit env variables in a file, that I can pipe easily to the cli. it is basically the same as piping the env variables themselves, but this way i can pipe them as bulk"

## Clarifications

### Session 2026-09-21

- Q: When a command runs, should it automatically pick up values from stored config files, or should applying them be an explicit action each session? → A: Explicit: `ome-zarr-tools` itself gains a top-level `--env-file PATH` option that supplies default values for that invocation only (explicit flags still override); no file is ever read from a fixed/implicit location. The `config` command's own `--user`/`--project` scope selector is removed — every `config` subcommand instead takes a required file-path parameter naming exactly which file to operate on.
- Q: `config`'s own file-path parameter and the top-level `--env-file` option would otherwise share the same flag name for two different meanings (`ome-zarr-tools --env-file A config set --env-file B KEY=VALUE`) — should `config`'s stay a same-named `--env-file` flag, get a distinct flag name, or become a positional argument? → A: Positional argument. `config show ENV_FILE`, `config set ENV_FILE KEY=VALUE...`, `config reset ENV_FILE [KEYS...] [--all]` — no `--env-file` flag on `config` itself; the top-level `--env-file` option (FR-007) is the only thing with that name.
- Q: What happens when the same key appears more than once in one file (e.g. a hand-edited file)? → A: The last occurrence wins (matching shell/dotenv sourcing semantics), and a warning is printed naming the duplicated key, every time the file is read — not a silent override.
- Q: Should every key that doesn't match a known option be flagged as "unrecognized" (even unrelated variables the file might also hold, e.g. cloud credentials for remote store access), and how severe should that report be? → A: Only keys that look like they were meant for this tool (start with `OME_ZARR_TOOLS_`) but don't match anything known are flagged — other keys are left alone. Severity depends on context: `config` subcommands (show/set/reset) report it as an error-level message; a live command run via the top-level `--env-file` reports it as a warning-level message (non-blocking — the command still proceeds); the TUI's main menu screen shows the same warning below the command list.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Set defaults once, stop repeating flags (Priority: P1)

A user runs the same commands over and over with the same non-default option values (e.g. always `--voxel_size_unit nanometer`, always `--chunk_size 128`). They want to record these choices once, in a plain environment-variable file, and have a single run of `ome-zarr-tools` pick them all up at once instead of retyping the flags every time.

**Why this priority**: This is the entire point of the feature. Without it, the config command is just a different file format for the same dead-end behavior it has today (values that are written and read back, but never actually change what any command does).

**Independent Test**: Set one value in a named file via the config command, run an unrelated command pointed at that file without passing the corresponding flag, and confirm the command used the configured value instead of its built-in default.

**Acceptance Scenarios**:

1. **Given** no file exists yet at a chosen path, **When** the user runs `ome-zarr-tools config set settings.env OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE=128`, **Then** `settings.env` is created containing that line.
2. **Given** that file exists, **When** the user runs `ome-zarr-tools --env-file settings.env from_images ...` without passing `--chunk_size`, **Then** the command uses `128` as the chunk size.
3. **Given** that file exists, **When** the user runs `ome-zarr-tools --env-file settings.env from_images --chunk_size 32 ...` (explicit flag), **Then** the command uses `32` (explicit flag always wins over a value from the file).

---

### User Story 2 - Apply a whole set of settings in one shot (Priority: P1)

A user maintains several different setting profiles (e.g. one per project, or one for high-resolution vs. low-resolution work) and wants to switch between them by pointing at a different file, applying that file's entire set of settings in one action rather than passing many individual flags or exporting many individual environment variables one at a time.

**Why this priority**: This is the specific pain point named in the request: bulk application, not one-variable-at-a-time. It's what makes the env-var file more useful than just documenting "here are the env vars you can export yourself."

**Independent Test**: Prepare a file with several settings, run a command pointed at it, and confirm all of its values take effect together in that one run.

**Acceptance Scenarios**:

1. **Given** a file with three settings, **When** the user runs `ome-zarr-tools --env-file profile.env <command>`, **Then** all three settings are in effect together for that run, applied in one action.
2. **Given** that same file also sets a value the user overrides with an explicit flag on the command line, **When** the command runs, **Then** the explicit flag's value wins for that one setting while the file's other settings still apply.

---

### User Story 3 - Inspect and clean up a settings file (Priority: P2)

A user wants to see exactly which settings are stored in a given file before relying on it, and wants to remove settings that are no longer needed, or delete the file entirely.

**Why this priority**: Necessary for trust and maintainability, but the feature already delivers its core value (US1/US2) without it — this is about auditability, not the primary flow.

**Independent Test**: Set a few values in a file, view it, remove one, and confirm it no longer appears.

**Acceptance Scenarios**:

1. **Given** a file has several settings, **When** the user runs `ome-zarr-tools config show settings.env`, **Then** its contents are displayed.
2. **Given** a configured setting exists in that file, **When** the user runs `ome-zarr-tools config reset settings.env SOME_KEY`, **Then** that key no longer appears when the file is viewed again.
3. **Given** the file exists, **When** the user runs `ome-zarr-tools config reset settings.env --all`, **Then** the file is deleted entirely.

---

### Edge Cases

- What happens when `config show` or `config reset` is pointed at a file that doesn't exist? A clear error naming the missing path, rather than silently behaving as if the file were empty.
- What happens when `config set` is pointed at a file that doesn't exist yet? The file is created (this is the normal way a settings file comes into being).
- What happens when the top-level `--env-file` passed to `ome-zarr-tools` doesn't exist? A clear error before the subcommand runs, rather than silently falling back to built-in defaults.
- What happens when the file contains a line that isn't valid `KEY=VALUE` syntax (e.g. a stray line, no `=`)? The command reports which line is invalid and does not silently ignore or corrupt the rest of the file.
- What happens when a user tries to set a variable name that isn't a valid environment-variable identifier (must start with a letter or underscore, contain only letters/digits/underscores)? The command rejects it with a clear error before writing anything.
- What happens when a configured variable's value doesn't match the type the target option expects (e.g. a non-numeric value for a numeric option)? The command using it reports a clear error identifying the offending variable, the same way it would report a bad `--flag` value.
- What happens when a variable name in the file doesn't correspond to any known command option (e.g. a typo, or a leftover from a renamed option)? Only if it starts with `OME_ZARR_TOOLS_` (so it was clearly meant for this tool) is it flagged as unrecognized and preserved untouched — an unrelated variable the file might also hold (e.g. cloud credentials for remote store access) is left alone entirely. The severity of that flag depends on context (FR-016): an error-level message from a `config` subcommand, a non-blocking warning from a live command run, or the same warning shown on the TUI's main menu.
- What happens when the same key appears on more than one line in the same file? The last occurrence's value wins (matching shell/dotenv sourcing semantics), and a warning naming the duplicated key is printed every time the file is read — never a silent override.
- What happens to a hand-added comment or blank-line formatting in the file after a `config set` call? `config set` rewrites the whole file from its recognized `KEY=VALUE` pairs — comments and blank-line formatting are not preserved across a `set`, only the key/value data itself.
- What happens when `config reset` is called with neither keys nor `--all`, or with both? Rejected with a clear error before anything is removed — exactly one of the two forms is required (FR-004).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `config` command MUST manage a plain environment-variable file (one `KEY=VALUE` pair per line) instead of the current JSON file. Every `config` subcommand MUST take a required `ENV_FILE` positional argument naming exactly which file to operate on — there is no built-in default location, no `--user`/`--project` scope selector, and no `--env-file` flag on `config` itself (that name is reserved for the distinct top-level option in FR-007, to avoid the same-name-different-meaning collision it would otherwise create).
- **FR-002**: The `config show ENV_FILE` command MUST display the contents of the given file.
- **FR-003**: The `config set ENV_FILE KEY=VALUE...` command MUST accept one or more `KEY=VALUE` pairs after the file argument, creating the file if it does not already exist. A key already present in the file MUST have its existing line updated in place (never appended as a second line for the same key, which would just create the duplicate FR-015 has to warn about); a new key MUST be appended.
- **FR-004**: The `config reset ENV_FILE` command MUST accept either one or more keys to remove from that file, or `--all` to delete the file entirely. Exactly one of these two forms MUST be given — calling `reset` with neither (no keys and no `--all`) or with both MUST be rejected with a clear error before anything is removed, matching how the prior JSON-based command validated its own mutually-exclusive options.
- **FR-005**: The `config set` command MUST reject a key that is not a syntactically valid environment-variable name (letters, digits, underscores; must not start with a digit) with a clear error, and MUST NOT partially write the file when a pair in a multi-pair invocation is rejected.
- **FR-006**: Every environment variable name this feature manages MUST be scoped to the specific command and option it configures by default (e.g. distinguishing `extract`'s `--output_format` from `inspect`'s `--output_format`, which share an option name but mean unrelated things and currently collide in the built-in defaults view). Two options that mean different things MUST NOT ever be able to collide under the same variable name. The one deliberate exception: when two or more commands' options configure the literal same underlying preference (a policy a user would rationally want identical everywhere, not a fresh per-run choice), they MAY share one unscoped variable instead — currently `from_images` and `migrate`'s `--target_version` (both mean "which OME-NGFF spec version to write") and their `--chunks_per_shard` (both mean "sharding factor for Zarr v3 output"). Options that merely share a *name* and value type without meaning the same thing (e.g. `from_images`, `downsample`, and `upsample`'s `--num_levels` — each is an independent, per-invocation "how many levels this run adds," not a standing preference) remain separately scoped even though they look similar; sharing those would let one setting silently control unrelated runs.
- **FR-007**: `ome-zarr-tools` itself MUST accept a top-level `--env-file PATH` option (usable with any subcommand). When given, the CLI MUST read that file and use its `KEY=VALUE` pairs as the default values for the invoked subcommand's matching options, for that invocation only. An explicitly passed command-line flag MUST always override a value coming from `--env-file`. Omitting `--env-file` MUST behave exactly as today (built-in defaults only) — no file is ever read implicitly.
- **FR-008**: Only options that are optional (have a built-in default) and represent a reusable *setting* MUST be exposed as configurable environment variables — required options, output paths, and other genuinely per-invocation inputs MUST NOT be exposed this way (an env var can't meaningfully hold "the path for this one run").
- **FR-009**: If a value coming from `--env-file` is invalid for the option it targets (wrong type, out of range, etc.), the command MUST fail with a clear error naming the variable and the problem, not a generic or misleading failure.
- **FR-010**: The TUI's existing config screen and "built-in defaults" reference view MUST be updated: the user/project scope picker is removed in favor of a required file-path field, and the corrected, per-command-scoped variable names replace the current ones (which can silently hide a colliding option, as shown by the `output_format` case in FR-006).
- **FR-011**: `from_images`'s `--num_downsampling` option MUST be renamed to `--num_levels` before it is exposed as a configurable variable, so it shares its name with the equivalent, already-named `--num_levels` option on `downsample` and `upsample` (all three describe the same concept: how many extra resolution levels to build) instead of exposing three different names for one idea across the tool.
- **FR-012**: `inspect`'s `--format`/`output_format` two-choice option (`text` or `json`) MUST be replaced with a boolean `--json` flag before it is exposed as a configurable variable: passing `--json` selects JSON output, omitting it selects text output (the current default). This makes it a plain on/off setting like `downsample`'s `--label`, rather than a choice needing its own set of allowed string values.
- **FR-013**: `apply_mask`'s `--temporary_upsample` flag currently does nothing (mask resampling always happens automatically regardless of it). A flag that can be "configured" via a settings file while having no observable effect is not an acceptable end state. **Resolved during `/speckit-plan`** (see plan.md/research.md §1): the flag is removed entirely, rather than inventing new behavior for it — no design document or test anywhere in the codebase indicates what "temporary" was ever meant to select, and the constitution requires removing confirmed dead code rather than leaving it "for later." It does not appear in the configurable-variable table below.
- **FR-014**: `migrate` currently has no `--chunk_size` option at all (it preserves the source dataset's existing chunk shape; only `from_images` can rechunk on write). **Resolved during `/speckit-plan`** (see plan.md/research.md §2): `migrate` does NOT gain a `--chunk_size` option — adding real rechunking-during-migration behavior would be a genuine new feature (touching the conversion path, interacting with `--chunks_per_shard`), out of scope for a config-plumbing change. `from_images`'s `--chunk_size` therefore remains scoped exactly as originally proposed (`OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE`), not merged with anything.
- **FR-015**: Whenever this feature reads a `KEY=VALUE` file (`config show`, `config set`'s pre-write read, `config reset`, or the top-level `--env-file` at command-run time) and finds the same key on more than one line, it MUST use the last occurrence's value (matching standard shell/dotenv sourcing semantics) and MUST print a warning naming the duplicated key — every time the file is read with a duplicate present, not just once when the duplicate was created.
- **FR-016**: Whenever this feature reads a `KEY=VALUE` file and finds a key that starts with `OME_ZARR_TOOLS_` but does not match any known configurable variable (e.g. a typo, or a leftover from a renamed option), it MUST flag that key as unrecognized. A key that doesn't start with `OME_ZARR_TOOLS_` MUST NOT be flagged at all — the file may legitimately also hold unrelated variables (e.g. cloud credentials for remote store access) that are none of this feature's business. The flag's severity depends on where the file is being read: a `config` subcommand (`show`/`set`/`reset`) MUST report it as an error-level message; a live command run via the top-level `--env-file` MUST report it as a non-blocking warning (the command still proceeds); the TUI's main menu screen MUST show the same warning, displayed below the command list.

### Key Entities

- **Environment-variable file**: A plain-text file of `KEY=VALUE` lines (one per configured setting), at a path always named explicitly by the user — there is no implicit or default location.
- **Configurable setting**: An existing CLI option (on some command) that has a built-in default and represents a reusable preference; identified by a per-command-scoped environment variable name.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can record a setting once in a file and have it apply to a command by naming that file, with zero repeated flags, until they change or remove it.
- **SC-002**: A user can apply an entire saved set of settings (any number of variables) in a single action (one `--env-file` flag), rather than one variable at a time.
- **SC-003**: Two different options that happen to share a plain name (e.g. `extract` and `inspect`'s `output_format`) are never confused with each other — each can be configured independently, and viewing a settings file never silently hides one in favor of the other.
- **SC-004**: An explicitly passed command-line flag always overrides a value coming from `--env-file`, with no exceptions, so configuring a default never removes a user's ability to override it per-run.
- **SC-005**: Every config file operation names the exact file being read or written — no command silently reads from or writes to a location the user didn't specify.
- **SC-006**: A user who reuses an existing general-purpose env file (one that also holds unrelated variables, e.g. cloud credentials) never sees a false-positive "unrecognized" warning about those unrelated variables — only genuine mistakes in this tool's own variable names are flagged.

## Assumptions

- **No implicit file locations**: There is no built-in "user config" or "project config" path and no scope selector; every `config` subcommand and the top-level `--env-file` option always require the caller to name the file explicitly.
- **`--env-file` is a top-level option, distinct from `config`'s own positional argument**: The top-level flag belongs to `ome-zarr-tools` itself (recognized before the subcommand name), e.g. `ome-zarr-tools --env-file settings.env from_images ...`, and applies default values to whichever subcommand follows. `config`'s own subcommands instead take a required `ENV_FILE` positional argument (`config show settings.env`, not `config show --env-file settings.env`) — the two are deliberately never the same flag, so a line like `ome-zarr-tools --env-file A config set B KEY=VALUE` reads unambiguously (option before the subcommand applies defaults; the bare argument after `config set` is the file being edited).
- **File format is plain `KEY=VALUE`**: Not `export KEY=VALUE` shell syntax and not a full shell script — plain dotenv-style lines, the widely recognized convention for this kind of file, trivially usable both by this tool's own file-reading and by a user's own shell (`set -a; source <file>; set +a`) or other standard env-file tooling if they want to use it that way outside this CLI.
- **Naming convention**: Variable names are scoped as `OME_ZARR_TOOLS_<COMMAND>_<OPTION>` in upper snake case (e.g. `OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE`), decided directly from evidence in the current codebase (see the `output_format` collision in FR-006) rather than left open, since a non-scoped naming scheme has a demonstrated, concrete failure mode already. The FR-006 shared/unscoped exception drops the command segment entirely (`OME_ZARR_TOOLS_<CONCEPT>`, e.g. `OME_ZARR_TOOLS_TARGET_VERSION`) — today's two shared variables are both named explicitly in the table below, so this is only a naming rule for a hypothetical future addition, not something either of today's two needed inferred.
- **Proposed initial set of configurable variables**, derived from the same built-in defaults the current config TUI screen already surfaces (`collect_default_values()`), scoped per command except for the two genuinely-shared settings called out in FR-006:

  | Command | Option | Proposed variable | Current default |
  |---|---|---|---|
  | from_images | --voxel_size_unit | `OME_ZARR_TOOLS_FROM_IMAGES_VOXEL_SIZE_UNIT` | `micrometer` |
  | from_images | --num_levels (renamed from --num_downsampling, FR-011) | `OME_ZARR_TOOLS_FROM_IMAGES_NUM_LEVELS` | `0` |
  | from_images | --chunk_size (FR-014 resolved: not merged, migrate does not gain this option) | `OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE` | `64` |
  | from_images, migrate | --target_version (shared, FR-006) | `OME_ZARR_TOOLS_TARGET_VERSION` | `0.5` |
  | from_images, migrate | --chunks_per_shard (shared, FR-006) | `OME_ZARR_TOOLS_CHUNKS_PER_SHARD` | (none) |
  | extract | --level | `OME_ZARR_TOOLS_EXTRACT_LEVEL` | `0` |
  | extract | --output_format | `OME_ZARR_TOOLS_EXTRACT_OUTPUT_FORMAT` | `.ome.tif` |
  | apply_mask | --threshold | `OME_ZARR_TOOLS_APPLY_MASK_THRESHOLD` | `0.5` |
  | inspect | --json (renamed from --format/output_format, FR-012) | `OME_ZARR_TOOLS_INSPECT_JSON` | `false` |
  | downsample | --num_levels (independent quantity, not shared — see FR-006) | `OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS` | `1` |
  | downsample | --label | `OME_ZARR_TOOLS_DOWNSAMPLE_LABEL` | `false` |
  | upsample | --num_levels (independent quantity, not shared — see FR-006) | `OME_ZARR_TOOLS_UPSAMPLE_NUM_LEVELS` | `1` |
  | upsample | --smooth | `OME_ZARR_TOOLS_UPSAMPLE_SMOOTH` | (none) |

  Explicitly excluded: required options (e.g. `--voxel_size`, `--volume`, `--mask`), path/output options (e.g. every command's `--output`), and `apply_mask`'s `--temporary_upsample`, which no longer exists at all per FR-013's resolution (removed, not merely excluded from this table).
