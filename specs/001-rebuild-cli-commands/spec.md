# Feature Specification: Rebuild OME-Zarr Tools CLI Package

**Feature Branch**: `001-rebuild-cli-commands`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "re-create the whole package using best coding practice and a set of agreed-upon dependencies. look at the README.md for the expected commands, along with two new commands: interactive and migrate."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convert and Manage Datasets With a Reliable CLI (Priority: P1)

A researcher who processes microscopy data uses the `ome-zarr-tools` command-line tool to convert raw image stacks into OME-Zarr, extract regions from a pyramid, fix metadata, apply masks, and manage configuration. Today these commands work, but the underlying package is not built to a consistent standard (dependencies aren't pinned or agreed upon, code quality and option naming vary command to command). The researcher needs the same five capabilities (`from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`) available under a consistent, predictable command/option naming scheme, built on a dependable, well-tested, maintainable foundation so that upgrades, bug fixes, and new commands can be added with confidence. Exact option names may change from today's tool as part of making the interface consistent, but every capability the current tool offers must still be reachable.

**Why this priority**: This is the existing, in-daily-use surface of the tool. Nothing else matters if the rebuild breaks a command a researcher already depends on.

**Independent Test**: Can be fully tested by running each of the five existing subcommands against representative inputs (an image stack, an OME-Zarr pyramid, a config file) and confirming outputs and exit codes match documented behavior.

**Acceptance Scenarios**:

1. **Given** a directory of 2D image slices and a target voxel size, **When** the user runs `from_images`, **Then** a valid OME-Zarr dataset is created at the requested path with correct voxel size metadata.
2. **Given** an existing OME-Zarr pyramid, **When** the user runs `extract` with a corner and size, **Then** the requested sub-region is written to the requested output file format.
3. **Given** an OME-Zarr dataset with missing or incorrect metadata, **When** the user runs `fix_metadata`, **Then** the tool shows current values, accepts corrected values, and writes valid metadata (with a backup of the prior state).
4. **Given** an OME-Zarr volume and a mask dataset, **When** the user runs `apply_mask`, **Then** the mask is resampled to match each resolution level and applied to the volume in place.
5. **Given** a user or project configuration request, **When** the user runs `config show|set|reset`, **Then** the correct configuration file is read, written, or cleared.
6. **Given** invalid or missing required input, **When** any command is run, **Then** the tool exits with a non-zero status and a clear, actionable error message rather than an unhandled crash.

---

### User Story 2 - Discover Commands Through an Interactive Mode (Priority: P2)

A new or infrequent user does not remember the exact flags for a command (e.g., how to express a crop region for `extract`, or which options `from_images` needs). Instead of consulting the README, they run the tool in an interactive mode that opens a top-level menu listing every available subcommand (`from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`, `migrate`, `inspect`); choosing one launches that command's own step-by-step wizard, then either runs the command or shows the equivalent non-interactive command line for future reuse.

**Why this priority**: Directly requested by name ("interactive") and lowers the barrier to entry for the whole tool, but the tool is already usable non-interactively, so it ranks below preserving existing functionality.

**Independent Test**: Can be fully tested by launching interactive mode, selecting each available command in turn, supplying prompted values, and confirming the resulting action matches what the equivalent direct CLI invocation would do.

**Acceptance Scenarios**:

1. **Given** the user runs the `interactive` subcommand, **When** the session starts, **Then** the user is shown a complete menu of every available subcommand to choose from.
2. **Given** the user selects a command from the menu, **When** the tool launches that command's dedicated wizard and prompts for its required and optional inputs, **Then** previously entered or detected values are offered as defaults where available.
3. **Given** the user completes all prompts, **When** they confirm, **Then** the tool executes the command with the supplied values and reports success or failure the same way the direct CLI would.
4. **Given** the user is mid-session, **When** they cancel or interrupt, **Then** no partial or destructive action is taken.

---

### User Story 3 - Migrate an OME-Zarr Dataset Forward (Priority: P2)

A user has OME-Zarr datasets written against an older OME-NGFF specification version — which, per the specification itself, also means an older Zarr storage layout (OME-Zarr 0.4 is defined on Zarr v2; 0.5 and later move to Zarr v3) — and needs to bring them up to the version the tool currently targets (or another supported target) without hand-editing metadata or re-converting from source images. They run `migrate` against the dataset with a single target version, review what will change, and get an updated dataset plus a backup of the original metadata.

**Why this priority**: Directly requested by name ("migrate") and is the natural companion to `fix_metadata`, but affects a narrower set of users (those holding older datasets) than the core conversion/extraction workflow.

**Independent Test**: Can be fully tested by pointing `migrate` at a sample dataset written in an older supported layout and confirming the resulting dataset validates against the current target specification while preserving pixel data and pre-existing metadata values that still apply.

**Acceptance Scenarios**:

1. **Given** an OME-Zarr dataset in a supported older specification version, **When** the user runs `migrate`, **Then** the tool detects the current version, reports the source and target versions (and the storage-format change that target implies), and asks for confirmation before writing changes.
2. **Given** the user confirms the migration, **When** it completes, **Then** the dataset's metadata and array storage both validate against the target version's specification, and a backup of the original metadata is retained.
3. **Given** a dataset that is already at the target specification version, **When** the user runs `migrate`, **Then** the tool reports that no migration is needed and makes no changes.
4. **Given** a dataset in a layout the tool does not recognize or support, **When** the user runs `migrate`, **Then** the tool fails clearly without modifying the dataset.

---

### User Story 4 - Inspect a Dataset's Structure and Storage (Priority: P3)

A user has an OME-Zarr dataset — their own, a colleague's, or one downloaded from elsewhere — and needs to understand it before working with it further: how many resolution levels it has, how large it is on disk versus its logical (uncompressed) size, how it's chunked, and whether it uses sharding. Today this requires opening the store by hand (a file browser, `zarr` in a Python shell, or `du`) and piecing it together. They run `inspect` and get a single report covering the whole dataset and each resolution level.

**Why this priority**: Directly requested by name ("inspect"), and purely diagnostic — read-only, no risk to data — so it's valuable but not on the critical path of any conversion/extraction workflow; it ranks below the commands that create or modify datasets.

**Independent Test**: Can be fully tested by running `inspect` against a fixture dataset with known shapes, chunk sizes, and (where supported) sharding, and confirming the reported per-scale and overall figures match what's actually on disk.

**Acceptance Scenarios**:

1. **Given** a valid OME-Zarr dataset with multiple resolution levels, **When** the user runs `inspect`, **Then** the tool reports, per level: array shape, dtype, chunk shape, shard shape (or "none" if unsharded), on-disk (stored) size, and logical (uncompressed) size — plus a dataset-wide total on-disk size and total logical size.
2. **Given** a dataset using Zarr v3 sharding on some or all levels, **When** the user runs `inspect`, **Then** the shard shape is reported distinctly from the chunk shape for each sharded level.
3. **Given** a dataset with metadata problems `fix_metadata`/`migrate` would also flag, **When** the user runs `inspect`, **Then** it still reports whatever storage-level facts (sizes, chunks, shards) it can determine, and separately notes that metadata is invalid rather than refusing to run.
4. **Given** a path that does not exist or is not a Zarr store, **When** the user runs `inspect`, **Then** the tool exits non-zero with a clear message rather than a partial or malformed report.

---

### Edge Cases

- What happens when a required external tool dependency is missing at runtime (e.g., an optional format-reading library)? The command should fail with a message naming the missing dependency, not a stack trace.
- How does `extract` behave when the requested corner/size falls partially or fully outside the dataset bounds?
- How does `apply_mask` behave when no resolution level is shared between the volume and mask pyramids at all (not even after up/downsampling)?
- How does `interactive` mode behave when a prompted value fails validation (e.g., a non-numeric voxel size)?
- How does `migrate` behave if the process is interrupted partway through writing the updated dataset?
- How do commands behave when given a path that does not exist, is not a Zarr store, or is not writable?
- How does `inspect` behave on a very large or remote (`cloudpathlib`) dataset where computing exact on-disk size requires enumerating many objects — does it still complete, even if slower?
- How does `inspect` behave on a dataset where some resolution levels are present in metadata but missing from storage (or vice versa)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI MUST provide the five capabilities documented today — `from_images`, `extract`, `fix_metadata`, `apply_mask`, `config` — as subcommands. Command and option names MAY be redesigned from the current tool for consistency across commands, but every capability and use case the current tool supports MUST remain reachable and MUST be documented.
- **FR-002**: The CLI MUST provide a new `interactive` command that opens a top-level menu of every available subcommand (including `migrate`); selecting one launches that command's own step-by-step wizard for supplying its inputs, then runs it.
- **FR-003**: The CLI MUST provide a new `migrate` command that upgrades an existing OME-Zarr dataset to a supported target OME-NGFF specification version, updating both its OME metadata and its underlying Zarr storage format together as that target version requires (per the OME-NGFF specification, each version implies exactly one Zarr storage format — see FR-015).
- **FR-004**: Every command MUST validate its inputs before performing any destructive or write action, and MUST report validation failures with a clear, human-readable message.
- **FR-005**: Every command that modifies an existing dataset in place (`fix_metadata`, `apply_mask`, `migrate`) MUST create a recoverable backup of the metadata or data it is about to overwrite before writing changes.
- **FR-006**: The CLI MUST report success and failure via process exit codes (zero for success, non-zero for failure) suitable for scripting.
- **FR-007**: The `config` command MUST continue to support showing, setting, and resetting both user-level and project-level configuration as documented.
- **FR-008**: The package MUST include automated tests covering the success path and at least one failure path for each command.
- **FR-009**: The package's dependencies MUST be explicitly declared and version-constrained in the package's build configuration so that installs are reproducible.
- **FR-010**: The package MUST expose a single console-script entry point (`ome-zarr-tools`) that dispatches to all subcommands, matching the invocation pattern `ome-zarr-tools [subcommand] [OPTIONS]` shown in the README.
- **FR-011**: The `interactive` command MUST allow the user to cancel before any command executes, leaving no side effects.
- **FR-012**: The `migrate` command MUST detect the dataset's current OME-NGFF specification version and, when it already matches the requested target version, exit without making changes.
- **FR-013**: Documentation (README) MUST be updated to describe all eight commands (`from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`, `interactive`, `migrate`, `inspect`), their options, and a migration guide for any renamed options from the previous version of the tool.
- **FR-014**: The rebuilt CLI's command and option names MAY differ from the current tool's; where they differ, the README MUST document the mapping from old to new so existing users can update their scripts.
- **FR-015**: The `migrate` command MUST accept a single target OME-NGFF specification version (e.g. `0.4`, `0.5`) and migrate both the OME metadata and the underlying Zarr array storage together to whatever that version's specification mandates (OME-Zarr 0.4 is defined on Zarr v2; 0.5 and later on Zarr v3) — metadata version and storage format are not independently selectable, since the specification itself couples them.
- **FR-016**: The `interactive` command MUST present a complete menu of all subcommands (`from_images`, `extract`, `fix_metadata`, `apply_mask`, `config`, `migrate`, `inspect`); it is a guided front-end that launches each command's own wizard rather than a separate dataset-browsing feature.
- **FR-017**: The CLI MUST provide a new `inspect` command that reports, for a given OME-Zarr dataset, per-resolution-level array shape, dtype, chunk shape, shard shape (when sharding is in use), on-disk (stored) size, and logical (uncompressed) size, plus dataset-wide totals for on-disk and logical size.
- **FR-018**: The `inspect` command MUST be read-only — it MUST NOT write to, back up, or otherwise modify the dataset it inspects.
- **FR-019**: The `inspect` command MUST support both a human-readable default output and a machine-readable (JSON) output mode, so its results can be consumed by scripts as well as read directly.

### Key Entities

- **OME-Zarr Dataset**: An on-disk (or remote) Zarr store containing pixel data at one or more resolution levels plus OME metadata describing axes, voxel size, and units.
- **Configuration File**: A JSON file, at user or project scope, holding key/value settings that influence command defaults.
- **Metadata Backup**: A timestamped snapshot of a dataset's prior root attributes, saved before any in-place metadata write.
- **Command Session (interactive mode)**: The sequence of prompts, entered values, and the resulting equivalent command invocation for a single interactive run.
- **Migration Record**: The detected source specification version, the requested target specification version (which implies a storage-format change), and outcome (migrated / already current / failed) of a single `migrate` invocation.
- **Inspection Report**: Per-level (shape, dtype, chunk shape, shard shape, stored size, logical size) and dataset-wide (total stored size, total logical size) facts produced by a single `inspect` invocation; read-only, not persisted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five existing capabilities produce correct, equivalent results on the same reference inputs before and after the rebuild (zero functional regressions), even where option names differ.
- **SC-002**: A user unfamiliar with the CLI can complete a full conversion (`from_images`) using only `interactive` mode's menu and wizard prompts, without consulting external documentation.
- **SC-003**: A dataset written against an older OME-NGFF specification version (and its correspondingly older Zarr storage format) is successfully brought to the target version via `migrate` with no loss of pixel data, verified by checksum or array-equality comparison before and after.
- **SC-004**: 100% of commands exit non-zero and print an actionable message (no unhandled stack trace) when given invalid input, across the automated test suite.
- **SC-005**: A fresh install from the package's declared dependencies succeeds reproducibly (same resolved versions) across repeated installs.
- **SC-006**: Automated tests cover at least the primary success path and one failure path for every command, and pass on every change before release.
- **SC-007**: A user can determine a dataset's per-level and total on-disk size, chunk shape, and shard shape using only `inspect`'s output — no separate file-browser, shell, or `zarr`-in-Python session needed.

## Assumptions

- "Best coding practice" is interpreted as: automated tests per command, explicit and version-constrained dependencies, consistent error handling and exit codes, consistent command/option naming, and updated documentation — not a specific framework or style guide, since none was named.
- The "agreed-upon set of dependencies" will be finalized during the planning phase (`/speckit-plan`), informed by the libraries already in use (click, dask, zarr, numpy, imageio, natsort, cloudpathlib, scikit-image, and optionally bioio-ome-zarr / ome-zarr-models); this spec does not mandate specific packages.
- Because command/option names may change, the rebuilt tool is not required to be a drop-in replacement for scripts written against the current CLI; FR-014 requires a documented old→new mapping to ease that transition instead.
- `migrate`'s default target is the OME-NGFF specification version the tool otherwise targets (currently 0.4, per the README); users may pass a different supported target version explicitly.
- Backups created by write operations are kept alongside the dataset (as today) rather than in a separate archive location.
- Interactive mode, migrate, and inspect are all invoked as subcommands of the same `ome-zarr-tools` entry point, not as separate executables.
- `inspect`'s default output is a human-readable table; `--format json` (or similar) is the scriptable alternative. Exact flag naming is an implementation detail for the planning phase.
- `inspect` computes on-disk size by asking the store/array layer for stored byte counts (e.g., `zarr`'s own size-accounting APIs) rather than an independent filesystem walk; for remote stores this may be slower since it still requires listing objects, but no separate opt-out is required for v1 (noted as an edge case, not a hard requirement).
