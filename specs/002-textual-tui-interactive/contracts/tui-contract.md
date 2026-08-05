# Phase 1 Contract: `interactive --tui`

This documents the interface the full-screen mode presents to users — its invocation, screens, footer shortcuts, and the per-command rich panels. It extends, but does not replace, `001-rebuild-cli-commands/contracts/cli-contract.md`'s `interactive` section.

## Invocation

```text
ome-zarr-tools interactive           # unchanged: line-by-line prompts (spec.md User Story 1)
ome-zarr-tools interactive --tui     # full-screen mode (spec.md User Story 2)
```

`--tui` requires both stdin and stdout to be attached to a real interactive terminal. If either is not a tty, the command exits non-zero with a message naming the problem (per `research.md`'s `isatty()` guard) and does **not** attempt to start Textual. Cross-cutting conventions from `cli-contract.md` (exit codes, no raw tracebacks) apply here too.

## Screens

1. **Command Menu** — an `OptionList` of every command `interactive` (no flag) also offers, in the same order. Selecting one moves to that command's Form screen. Escape or Ctrl+C from this screen exits the TUI with no side effects.

2. **Command Form** — one field per `selected_command.params` (§ Widget mapping), all visible and editable together (FR-004). **No button.** A persistent footer shows the Run / Copy / Copy-and-exit shortcuts (§ Footer shortcuts). The equivalent CLI invocation is shown live above/near the footer, recomputed on every field edit. `fix_metadata` and `migrate` additionally show the Diff/Rich View panel (§ Command-specific screens) in place of (or alongside) the plain field list — that panel *is* their form, per FR-018.

3. **Running** — once Run is pressed, the form's fields become read-only and a status area appears: a `ProgressBar` or animated `Sparkline` (§ Status indicator) plus a log, hidden by default and toggleable (§ Log). The Textual app does **not** exit at this point — it stays open, showing live status, for the duration of the command (research.md's worker-thread execution model). On completion (success or failure), the result is shown in the log; the user then exits the TUI themselves (e.g. Escape/Ctrl+C) — there is no automatic exit-on-success, so the final log output remains visible to read.

4. **Copy / Copy-and-exit hand-off** — Copy writes the equivalent invocation via `App.copy_to_clipboard` (OSC 52) *and* unconditionally appends it as a selectable line in the log (research.md: no reliable success/failure signal from the OS-clipboard attempt, so both always happen). Copy-and-exit does the same, then exits the TUI. Neither runs anything.

## Footer shortcuts (replaces the old confirmation-dialog design)

| Shortcut | Screen | Effect |
|---|---|---|
| Run | Command Form (all required fields filled) | Executes immediately in a worker thread; no confirmation dialog — the live invocation text already shown *is* the confirmation (FR-005). Disabled/no-op if a required field is empty. |
| Copy | Command Form | Copies the equivalent invocation (OSC 52 best-effort + always-shown log line); does not run anything. |
| Copy-and-exit | Command Form | Same copy, then closes the TUI. |
| Toggle log | Command Form, Running | Shows/hides the `Command Log` panel; never pauses or clears it (FR-015). |
| Back | Command Form | Returns to Command Menu (Escape), discarding the current form's in-progress values. |
| Quit | Menu, Form, Running | Ctrl+C from any screen exits the TUI; before Run this makes no changes (FR-005); once a command is running, this feature does not define mid-flight cancellation (spec.md Assumptions) — Ctrl+C after Run has been pressed only closes the TUI once the command's own process has finished. |

Exact key bindings (which physical key maps to which shortcut above) are an implementation detail (spec.md Assumptions) as long as every shortcut is discoverable via the persistent footer.

## Widget mapping

See `research.md` § Widget mapping for the full `click.Parameter` → Textual widget table. Unchanged from the pre-clarify design:

| Parameter kind | Widget |
|---|---|
| Argument / Option, path type | `Input` + `SafePathAutoComplete` |
| Option, flag | `Checkbox` |
| Option, `click.Choice` | `Select` |
| Option, `multiple`/`nargs>1` | `Input`, space-separated |
| Option, everything else | `Input`, pre-filled with the CLI default |

## Path autocomplete behavior (FR-008, FR-009, FR-013)

Unchanged from the pre-clarify design — suggestions filter live inline; no match found leaves the field editable; a directory that can't be listed (e.g. permission-denied entries) degrades to no suggestions rather than crashing (`SafePathAutoComplete`, research.md).

## Status indicator (FR-014)

- Starts **indeterminate**: an animated `Sparkline` fed a rolling buffer of synthetic activity values on a timer.
- Becomes **quantified** the first time the worker thread's registered `dask.callbacks.Callback` reports a task total (`start_state`); switches to a `ProgressBar` showing `done`/`total`, advancing on each `posttask`. Never reverts to indeterminate once quantified.
- Commands that perform no dask work (e.g. `config`, `inspect`) simply stay indeterminate for their (typically brief) run.

## Log (FR-015)

- Hidden by default; toggled via the log shortcut, independently of the status indicator.
- Populated by redirecting `stdout` during the worker-thread command execution — the same text a plain-CLI run of the same command would print via `click.echo`, captured rather than lost to terminal scrollback.
- Also receives the Copy/Copy-and-exit fallback line (§ Copy hand-off above) and the final success/failure result line.

## Command-specific screens

### `inspect` (FR-016)

Read-only. Two switchable panels (keyboard shortcut, not simultaneous — spec.md Assumptions):
- **JSON panel**: one scrollable, syntax-highlighted `TextArea(language="json", read_only=True)` block per resolution level, matching `inspect`'s own `build_report` per-level content (`001-rebuild-cli-commands`).
- **Summary panel**: the same structure figures `inspect`'s default text output reports (shapes, chunk/shard layout, sizes, totals).

### `config` (FR-017)

- A scope picker (user/project, matching CLI `--user`/`--project`).
- For the selected scope: current effective values (as `config show` would report), the tool's built-in defaults shown alongside for comparison, and a `TextArea(language="json")` editor for that scope's config file.
- Save validates JSON syntax and the same semantics `config set` already enforces (`ome_zarr_tools.commands.config`); invalid input blocks saving without discarding the in-progress edit (Edge Cases).

### `fix_metadata` / `migrate` (FR-018, FR-019)

- **Always** shown, every run, before Run is meaningfully pressable: a Diff View (`before`/`after` JSON, unified-diff-styled) and a Rich View/Edit Surface.
- `fix_metadata`: the rich view is a `TextArea(language="json")`, directly editable — this *replaces* one-field-at-a-time prompting; edits are validated the same way the CLI's own write-time validation works, flagged inline before Run can act (FR-018).
- `migrate`: the rich view is a read-only formatted preview (`preview_migration`, computed against an in-memory `zarr.storage.MemoryStore` — research.md), recomputed whenever `--target_version` changes.
- Run, once pressed, executes the real, unmodified CLI command (`fix_metadata`/`migrate`) with the tokens built from the (possibly edited) form/rich-view state — no separate confirmation beyond the diff/rich view already having been shown (FR-019).

## Failure modes

| Condition | Behavior |
|---|---|
| `--tui` passed without an attached interactive terminal | Non-zero exit, clear message, no Textual startup attempted (FR-010, SC-004) |
| Terminal resized mid-session | Textual's built-in reflow handles this; no data loss to in-progress field values |
| Terminal too small for the current form | Textual's built-in scrolling applies; all fields/panels remain reachable via keyboard navigation |
| Required field left empty when Run is pressed | Run is a no-op; the empty required field is focused/highlighted |
| Copy's OSC 52 attempt unsupported by the terminal/SSH session | No detectable failure (research.md) — the log line is shown unconditionally regardless, so nothing is ever silently lost |
| Command raises during execution (worker thread) | Caught, shown as a failure result in the log; the TUI does not crash |
| `fix_metadata` rich-view edit fails validation | Flagged inline in the Rich View/Edit Surface; Run is a no-op until corrected |
| `config` editor JSON is invalid | Save blocked, syntax error shown, in-progress edit preserved |
