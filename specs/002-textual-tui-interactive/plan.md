# Implementation Plan: Textual-Based TUI for Interactive Mode

**Branch**: `002-textual-tui-interactive` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-textual-tui-interactive/spec.md`

## Summary

Add an opt-in, full-screen terminal UI to the existing `interactive` command, reached via `interactive --tui` (default invocation keeps today's line-by-line prompts, per FR-001/FR-011). This plan supersedes the version written before `/speckit-clarify` substantially expanded the design: **no Button widget** — every command's form is driven by footer-displayed keyboard shortcuts (**Run**, **Copy**, **Copy-and-exit**), Run executes immediately with the equivalent CLI invocation already visible rather than a confirmation dialog (FR-005), and every command gets a live status indicator (`ProgressBar` or an animated `Sparkline`) plus a toggleable log. `inspect`, `config`, `fix_metadata`, and `migrate` each get command-specific rich panels (FR-016–FR-018).

The key architectural finding from this planning pass: **none of this requires modifying 001's already-shipped command implementations to report progress or expose internal hooks.** Commands still run through the exact same generic path the original TUI design used — `command.main(args=tokens, standalone_mode=False)` — just inside a Textual worker thread instead of blocking the UI. Progress comes from registering a `dask.callbacks.Callback` around that call, which observes any dask task graph the command happens to execute (from_images, extract, apply_mask, and migrate's `ngff-zarr` internals all use dask) with zero per-command code changes. The log comes from redirecting stdout during that same call. `fix_metadata` and `migrate`'s diff/rich-view previews are computed by the TUI calling the same pure logic (a small, behavior-preserving extraction from each command, mirroring the already-proven `_confirm_and_run` extraction pattern) or the same third-party library (`ngff-zarr`, writing its preview to an in-memory `zarr.storage.MemoryStore` — verified working, zero filesystem I/O) that the real command already uses — never invoking a half-run of the real command itself. See `research.md` for the verification behind every one of these decisions.

## Technical Context

**Language/Version**: Python ≥3.10 (unchanged)

**Primary Dependencies**: `textual>=8.0`, `textual-autocomplete>=4.0` (unchanged from the pre-clarify plan). **No new dependencies** — `ProgressBar`, `Sparkline`, `TextArea` (with built-in `json` language support), and `RichLog` are all part of `textual` already installed; diffing uses the stdlib `difflib`; progress uses `dask` (already a core runtime dependency of the whole package, per `001-rebuild-cli-commands`).

**Storage**: N/A (no new persistent state). `migrate`'s diff/rich-view preview is computed into an in-memory `zarr.storage.MemoryStore` — verified working — and discarded; nothing touches disk until Run invokes the real `migrate` command.

**Testing**: `pytest` + `pytest-asyncio` (unchanged) via Textual's `App.run_test()`/`Pilot`, extended to cover: worker-thread command execution and its progress/log callbacks (using `pilot.pause()` to let the worker and `call_from_thread` callbacks settle), the diff/rich-view preview functions in isolation (pure functions, no Textual needed), and the footer shortcuts (Run/Copy/Copy-and-exit) replacing the old Button-click tests.

**Target Platform**: Unchanged — Linux/macOS terminal, `--tui` requires an attached interactive terminal.

**Project Type**: Single project — CLI tool (Option 1, unchanged)

**Performance Goals**: The UI thread must stay responsive (able to redraw the status indicator and accept a cancel/quit keypress) for the full duration of a running command — achieved by always running `command.main()` in a Textual worker thread (`run_worker(..., thread=True)`), never on the main event loop, verified working with `App.call_from_thread` for the progress/log callbacks it needs to push back.

**Constraints**: (unchanged) FR-001's prompt-based flow must not regress. (new) Extracting `fix_metadata`'s proposed-metadata-building logic and `migrate`'s version-detection/preview logic into reusable, pure functions MUST NOT change either command's existing CLI behavior or test results — these are refactors verified by rerunning `001-rebuild-cli-commands`'s existing test suite unchanged, the same discipline already used for the `_confirm_and_run` extraction.

**Scale/Scope**: Single-user, single-session TUI; the same 8 commands; one command's form (now with status/log/diff panels as applicable) at a time.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still the unfilled template — no gates apply (same finding as both prior plans in this repo).

## Project Structure

### Documentation (this feature)

```text
specs/002-textual-tui-interactive/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── tui-contract.md   # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── ome_zarr_tools/
    ├── cli.py                       # unchanged
    ├── commands/
    │   ├── interactive.py           # MODIFIED: --tui flag/entry point unchanged, but
    │   │                             # _run_tui's body is simplified -- the TUI now runs
    │   │                             # commands itself (worker thread) instead of exiting
    │   │                             # and deferring to _confirm_and_run post-exit; that
    │   │                             # helper remains used by the prompt-based path only
    │   │                             # -- see research.md
    │   ├── fix_metadata.py          # MODIFIED (safe extraction): proposed-multiscales-
    │   │                             # building logic pulled into a reusable pure function,
    │   │                             # used by both the existing prompt flow and the TUI's
    │   │                             # diff preview; CLI behavior unchanged
    │   └── migrate.py               # MODIFIED (safe extraction): version-detection and
    │                                 # preview-building logic pulled into reusable functions;
    │                                 # CLI behavior unchanged
    └── tui/
        ├── __init__.py
        ├── app.py                   # Command Menu screen + per-command Form screen shell
        ├── fields.py                 # click.Parameter -> widget mapping (unchanged from
        │                             # pre-clarify: Input/Checkbox/Select/PathAutoComplete)
        ├── execution.py              # NEW: run a click.Command in a worker thread; dask
        │                             # Callback -> progress; stdout redirect -> log; both
        │                             # pushed to the UI thread via call_from_thread
        ├── status.py                  # NEW: ProgressBar/Sparkline status widget + toggleable
        │                             # RichLog, driven by execution.py's callbacks
        ├── diff.py                    # NEW: difflib-based diff rendering (RichLog) +
        │                             # fix_metadata/migrate preview-computation helpers
        └── screens/
            ├── __init__.py
            ├── inspect_screen.py      # NEW: JSON-per-level panel + structure-summary panel
            ├── config_screen.py       # NEW: scope picker + current/defaults view + TextArea
            │                         # JSON editor
            └── metadata_screen.py     # NEW: fix_metadata/migrate's diff view + rich
                                      # view/edit TextArea, built on diff.py

tests/
├── contract/
│   └── test_interactive_tui.py     # --tui flag surface, no-tty fallback, widget mapping,
│                                    # footer shortcut presence (no Button)
└── integration/
    ├── test_interactive_tui.py      # menu -> form -> autocomplete -> Run/Copy/Copy-and-exit
    │                                 # -> cancel, now via footer shortcuts instead of a button
    ├── test_tui_execution.py         # NEW: worker-thread execution, dask-Callback progress,
    │                                 # stdout-capture log, against real (small) commands
    ├── test_tui_diff.py              # NEW: fix_metadata/migrate preview functions (pure,
    │                                 # no Textual needed) + diff rendering
    └── test_tui_screens.py           # NEW: inspect/config/metadata screen-specific panels
```

**Structure Decision**: Single-project CLI (Option 1), unchanged. `tui/` grows from two modules to a small package: `execution.py` and `status.py` are cross-cutting (used by every command's Form screen), `diff.py` and `screens/` hold the four command-specific rich views called out in the spec. `fix_metadata.py` and `migrate.py` each get one small, behavior-preserving extraction — no other `001` command changes.

## Complexity Tracking

*No constitution gates are defined (see Constitution Check above), so no violations require justification.*

| Addition | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Worker-thread execution (`tui/execution.py`) instead of the pre-clarify plan's "exit the TUI, then run" | FR-014/FR-015 require a *live* status indicator and log while the command runs — impossible if the TUI has already exited before the command starts. | Keeping the old "exit-then-run" model — rejected, it can't satisfy FR-014/FR-015 at all, not just less elegantly. |
| Extracting small pure functions from `fix_metadata.py`/`migrate.py` | FR-018's diff/rich-view preview needs the real proposed-metadata content before Run, without performing a real write. | Duplicating each command's metadata-building logic inside the TUI instead of extracting it — rejected as a maintainability risk (the two copies could silently drift); calling the real CLI command early and discarding its result — rejected as more invasive (still writes to disk, needs its own cleanup, and duplicates work Run would repeat anyway) than the in-memory/pure-function approach chosen. |
