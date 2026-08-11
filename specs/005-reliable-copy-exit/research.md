# Phase 0 Research: Reliable Copy & Exit

## Decision: Propagate the invocation via `App.exit(result=...)`, print after `App.run()` returns

**Decision**: `InteractiveTUIApp` becomes `App[str | None]`. Every screen's
`action_copy_and_exit()` changes from `self.app.exit(result=None)` to
`self.app.exit(result=self._invocation_text())` (each screen already has an
`_invocation_text()`/equivalent method feeding the existing clipboard-copy
attempt — no new computation, just reusing it as the exit result too).
`commands/interactive.py`'s `app.run()` call captures that return value and,
once `run()` has returned, prints it via `click.echo()`:

```python
invocation = app.run()
if invocation:
    click.echo(f"Copied invocation: {invocation}")
```

**Rationale**: `App.run()` is a blocking call that returns only after Textual's
`run_async()` fully completes, which includes tearing down the alt-screen
buffer and restoring the terminal to normal mode (verified by reading
`textual/app.py`'s `run()`/`run_async()`). Printing only *after* `run()`
returns therefore guarantees the terminal is back in normal mode and the
printed line becomes part of the user's regular scrollback — not something
written into (and potentially lost with) the alt-screen buffer. Using
`click.echo()` — the same output mechanism every other command in this CLI
already uses — keeps the printed output composable with Click's own stream
handling and directly testable via `click.testing.CliRunner`, consistent
with how every other command in this codebase is tested.

**Alternatives considered**:
- *Print from inside the Textual app, just before calling `self.app.exit()`*
  — rejected. At that point the app is still mid-shutdown; Textual's driver
  has not necessarily restored the main screen buffer yet, so the printed
  text could be invisible (still inside the alt-screen) or subsequently
  cleared once teardown actually completes. This is exactly the class of
  "trust the framework's own teardown boundary" bug this feature exists to
  avoid repeating.
- *Write the invocation to a file* — rejected. Adds a file the user has to
  separately know about and locate; contradicts the spec's requirement that
  retrieval happens via "normal terminal text selection" (FR-002/SC-002).
- *Use Textual's `self.notify(...)`* — rejected. Notifications render only
  while the app is still running and disappear once it exits — the exact
  same visibility problem as the existing on-screen log, not a fix for it.

## Decision: One-line change per call site, no new shared helper

**Decision**: No new shared function is introduced. Each of the 5
`action_copy_and_exit()` implementations already calls `self.action_copy()`
(which itself already computes the invocation via each screen's own
`_invocation_text()`) followed by `self.app.exit(result=None)`. The only
change per site is the `exit()` call's argument.

**Rationale**: Each screen already has exactly the string this feature needs,
computed by exactly the same logic the clipboard-copy attempt already uses
(spec requirement FR-005: "reproduce the invocation text exactly"). Reusing
it via one changed line per site is the smallest possible diff (constitution
Principle I) and carries zero risk of the printed and copied strings drifting
apart, since they're now provably the same call.

**Alternatives considered**: A shared `copy_and_exit_with_fallback(screen)`
free function — rejected as unnecessary indirection for a one-line change
repeated 5 times; the existing per-screen `action_copy_and_exit()` methods
already are the natural, minimal place for this.

## Decision: `click.echo()`, not `print()`

**Decision**: Use `click.echo()`.

**Rationale**: Every other command in this codebase already outputs via
`click.echo()` (never bare `print()`), which correctly interacts with
`click.testing.CliRunner`'s output capture (used throughout the existing test
suite) and Click's own stream/color handling. Using bare `print()` here would
be inconsistent with the rest of the codebase and untestable via the same
`CliRunner` pattern every other command's tests already use.
