# Specification Quality Checklist: Config Command Uses Env-Var Files

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The one open architectural fork (automatic vs. explicit application) was
  resolved during drafting: a required top-level `--env-file PATH` option on
  `ome-zarr-tools` supplies default values for that invocation only; the
  `config` command's `--user`/`--project` scope selector was removed in favor
  of a required file-path parameter on every `config` subcommand. See the
  `## Clarifications` section in spec.md. All items pass; ready for
  `/speckit-plan`.
- FR-013 deliberately leaves one decision open (fix `apply_mask`'s
  `--temporary_upsample` no-op vs. remove it entirely) rather than picking
  one now. This isn't a `[NEEDS CLARIFICATION]` marker since it doesn't block
  planning — either resolution is compatible with the rest of this spec — but
  `/speckit-plan` MUST pick one, and `/speckit-analyze` MUST verify the plan
  and tasks actually resolved it (not just carried the no-op forward
  unchanged) before implementation begins.
- FR-014 similarly defers a second decision: whether `migrate` gains a
  `--chunk_size` option at all (it currently has none). `/speckit-plan` MUST
  decide this, and if the answer is yes, MUST merge it with `from_images`'s
  `--chunk_size` into one shared `OME_ZARR_TOOLS_CHUNK_SIZE` variable rather
  than keeping two scoped ones — `/speckit-analyze` MUST verify whichever
  outcome was chosen is reflected consistently in the plan, tasks, and the
  final variable table.
- `/speckit-clarify` session (2026-09-21, second pass) resolved three more
  ambiguities, all now in `## Clarifications` and reflected in the FRs/Edge
  Cases: (1) `config`'s file parameter is a positional `ENV_FILE` argument,
  never a `--env-file` flag, to avoid colliding with the distinct top-level
  `--env-file` option (FR-001-004); (2) a duplicated key within one file uses
  last-line-wins semantics with a warning on every read (FR-015); (3) only
  `OME_ZARR_TOOLS_`-prefixed unknown keys are flagged, with severity varying
  by context — error in `config` subcommands, non-blocking warning from a
  live command run, and a warning shown below the TUI's main menu (FR-016,
  SC-006). All checklist items still pass; ready for `/speckit-plan`.
- `/speckit-plan` (2026-09-21) resolved FR-013 (remove `--temporary_upsample`)
  and FR-014 (do not add `migrate --chunk_size`) — see plan.md/research.md.
- `/speckit-analyze` (2026-09-22) found spec.md's own FR-013/FR-014 text and
  variable table had not been updated to match that resolution, plus several
  coverage gaps (FR-009 untested; FR-016's `config set` bucket unimplemented/
  untested; FR-016's live-run warning and FR-015's `config set`/`--env-file`
  duplicate handling untested; FR-004's neither/both `reset` case unspecified)
  and two stale cross-references (FR-010 mis-cited for FR-009's behavior in
  data-model.md and cli-contract.md; plan.md's Project Structure listed a test
  file tasks.md never creates). All findings remediated same-day: spec.md's
  FR-013/FR-014/FR-004 text and table updated, two new Edge Cases added
  (comment loss on `config set`, reset neither/both), naming-convention note
  added for shared variables (D1), plan.md/data-model.md/cli-contract.md
  citations and paths fixed, and tasks.md T009-T012/T020/T023 extended with
  the missing test/implementation coverage. Re-verified: no
  `[NEEDS CLARIFICATION]` markers, no stale "pending FR" text, table row count
  matches data-model.md's 13-entry registry. Ready for `/speckit-implement`.
