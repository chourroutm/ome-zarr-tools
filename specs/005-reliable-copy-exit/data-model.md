# Phase 1 Data Model: Reliable Copy & Exit

No persistent data entities are involved — this feature carries one ephemeral
value through an existing, already-typed but previously-unused channel.

## Copy & Exit Result

**Represents**: The CLI invocation string a per-command screen's "Copy & exit"
shortcut both attempts to place on the clipboard and, now, returns as the
app's exit result so it can be printed once the terminal is back in normal
mode.

**Representation**: `InteractiveTUIApp(App[str | None])` (was `App[None]`).
Each screen's `action_copy_and_exit()`:

```python
def action_copy_and_exit(self) -> None:
    self.action_copy()  # unchanged: attempts App.copy_to_clipboard()
    self.app.exit(result=self._invocation_text())
```

`commands/interactive.py`'s `--tui` path:

```python
invocation = app.run()
if invocation:
    click.echo(f"Copied invocation: {invocation}")
```

**Relationships**: `_invocation_text()` (or each screen's equivalent — every
screen already has one, since it's what the existing clipboard-copy attempt
already uses) is the single source of truth; both the clipboard write and
the exit result read from it, so they can never disagree (FR-005).

**Lifecycle**: Computed fresh at the moment "Copy & exit" is pressed →
passed to `App.copy_to_clipboard()` (existing, unchanged) → passed to
`App.exit(result=...)` → returned by the blocking `App.run()` call once
Textual's shutdown (including terminal restoration) is complete → printed via
`click.echo()`. Every other exit path (`Cancel`, `Back` at the menu, plain
"Copy" without exiting, a Result screen's return-to-form) continues to exit
with `result=None`, so nothing is printed — the printed fallback is specific
to "Copy & exit," per FR-006 and the spec's own scope assumption.
