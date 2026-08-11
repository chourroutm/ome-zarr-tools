# Implementation Plan: Reliable Copy & Exit

**Branch**: `005-reliable-copy-exit` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-reliable-copy-exit/spec.md`

## Summary

Every per-command TUI screen's "Copy & exit" shortcut currently only attempts
`App.copy_to_clipboard()`, which writes an OSC 52 terminal escape sequence —
silently ineffective on terminals/multiplexers (notably tmux/screen over SSH,
this tool's primary shared-HPC environment) that don't pass it through, with
no error shown. This feature adds an unconditional fallback: after the app
exits, the exact CLI invocation is printed to the real terminal (not the
TUI's own on-screen log, which disappears on exit), so the user can always
retrieve it via normal text selection. The clipboard attempt is unchanged;
plain "Copy" (no exit) is unaffected, since the app keeps running afterward.

Mechanism: `InteractiveTUIApp` becomes `App[str | None]` and each
`action_copy_and_exit()` calls `self.app.exit(result=invocation)` instead of
`result=None`; `commands/interactive.py`'s `app.run()` call captures that
return value and, once Textual has torn down the alt-screen and restored the
normal terminal (which `App.run()` returning already guarantees), prints it
via `click.echo()` — the same output mechanism every other command already
uses, so it composes correctly with `CliRunner`-based tests and doesn't bypass
Click's stream handling.

## Technical Context

**Language/Version**: Python >=3.10 (repository baseline, `pyproject.toml`)

**Primary Dependencies**: `click` (CLI/output), `textual` (TUI framework) — both already in use; no new dependency

**Storage**: N/A

**Testing**: `pytest` + Textual's `App.run_test()`/`Pilot` for TUI behavior (existing pattern), `click.testing.CliRunner` for the printed-output-after-exit check

**Target Platform**: Linux/macOS terminal, including SSH + tmux/screen sessions on shared HPC systems (the environment this feature specifically targets)

**Project Type**: Single project — CLI/TUI tool (existing `src/ome_zarr_tools/` layout, no new top-level structure)

**Performance Goals**: N/A — one `click.echo()` call on exit, no measurable cost

**Constraints**: Must not change plain "Copy" (no-exit) behavior; must apply uniformly to all 5 existing `action_copy_and_exit()` implementations; must not weaken or replace the existing clipboard-copy attempt

**Scale/Scope**: `tui/app.py` (`InteractiveTUIApp`, `CommandFormScreen`), `tui/screens/inspect_screen.py`, `tui/screens/metadata_screen.py` (`_BaseMetadataScreen`, `_BaseConfirmScreen`), `tui/screens/config_screen.py`, `commands/interactive.py` — 5 screen classes + 1 app class + 1 CLI command function

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Code Quality)**: No new abstractions beyond a shared helper for
  "build the invocation and exit with it" if the 5 call sites turn out
  identical enough to warrant one (evaluated in Phase 1 design, not assumed
  up front) — otherwise each screen's existing `action_copy_and_exit()` gets
  a one-line change (`result=None` → `result=self._invocation_text()`).
  `ruff`/`mypy` clean is a hard gate. PASS.
- **Principle II (Test-First, NON-NEGOTIABLE)**: Every screen's changed
  `action_copy_and_exit()` needs a failing-then-passing test asserting
  `App.run_test()`'s exit result carries the invocation; `interactive.py`'s
  print-on-exit needs a `CliRunner`-based test asserting the invocation
  appears in `result.output`. Tasks below are test-first. PASS.
- **Principle III (Deliberate Commit Discipline)**: No commits will be made
  during this workflow unless the user explicitly asks. PASS.
- **TUI/UI manual verification gate**: Since this changes exit-time terminal
  output (something a headless `Pilot` test can partially but not fully
  represent — `CliRunner.invoke()` captures `click.echo()` output correctly,
  but doesn't prove a *real* terminal shows it after Textual's alt-screen
  teardown), quickstart.md includes a real-terminal manual check as a
  follow-up item, consistent with spec 004's T053 precedent.

No violations. Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/005-reliable-copy-exit/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/ome_zarr_tools/
├── commands/
│   └── interactive.py         # MODIFIED: app.run() return value -> click.echo() fallback print
└── tui/
    ├── app.py                  # MODIFIED: InteractiveTUIApp -> App[str | None];
    │                           # CommandFormScreen.action_copy_and_exit()
    └── screens/
        ├── inspect_screen.py    # MODIFIED: InspectScreen.action_copy_and_exit()
        ├── metadata_screen.py   # MODIFIED: _BaseMetadataScreen.action_copy_and_exit()
        │                        # (fix_metadata/migrate Form), _BaseConfirmScreen's
        │                        # (fix_metadata/migrate Confirm, spec 004 US8)
        └── config_screen.py     # MODIFIED: ConfigScreen.action_copy_and_exit()

tests/
├── integration/
│   ├── test_tui_copy_exit.py   # NEW: per-screen App.run_test() exit-result assertions
│   └── test_interactive.py     # MODIFIED (or new test in same file): CliRunner-based
│                                 # assertion that the invocation is printed after --tui exits
```

**Structure Decision**: Single existing project, no new top-level directories.
Every change lands in an already-modified-this-session file (spec 004's work
touched all of these except `commands/interactive.py`), consistent with
Principle I's "prefer editing existing modules."

## Complexity Tracking

*No violations — table omitted.*
