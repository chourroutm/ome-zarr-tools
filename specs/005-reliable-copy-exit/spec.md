# Feature Specification: Reliable Copy & Exit

**Feature Branch**: `005-reliable-copy-exit`

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: "Add a reliable fallback for the TUI's "Copy" and "Copy & exit" shortcuts. Currently these call Textual's copy_to_clipboard(), which writes an OSC 52 terminal escape sequence -- this only works if the terminal emulator supports OSC 52 and, when running inside tmux/screen, if the multiplexer is configured to pass it through. On a shared HPC system accessed via SSH+tmux this commonly fails completely silently: no error is shown, but nothing ends up on the clipboard. Keep the existing clipboard-copy attempt (it's free and works great when supported), but add printing the exact CLI invocation string to stdout after the app exits, for every place "Copy & exit" (or exiting after a Copy) is used across the TUI's per-command screens, so the user always has a reliable way to retrieve the invocation via normal terminal text selection even when clipboard copy silently failed."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Always able to retrieve the command after Copy & exit (Priority: P1)

A user fills in a command's fields in the TUI and presses "Copy & exit" to grab
the equivalent CLI invocation and leave the app. Today, this silently attempts
to place the invocation on the system clipboard via a terminal escape
sequence — on a shared HPC system reached over SSH and a terminal
multiplexer (tmux/screen), that escape sequence is very often not passed
through to a real clipboard, and nothing visibly indicates this failed. The
user is left back at their shell prompt with nothing to paste. Now, after the
app exits, the exact invocation text is also printed to the terminal, so the
user can always retrieve it by selecting the printed line — whether or not
the clipboard attempt actually worked.

**Why this priority**: This is the entire feature — without it, "Copy & exit"
remains silently unreliable on the exact environment (shared HPC, SSH,
tmux/screen) this tool is built for.

**Independent Test**: On any per-command screen, fill in fields, press
"Copy & exit", and confirm that once the app has exited, the terminal shows
the exact CLI invocation as plain text — independent of whether the terminal
happens to support the clipboard escape sequence.

**Acceptance Scenarios**:

1. **Given** a user has filled in a command's fields, **When** they press
   "Copy & exit", **Then** the app exits and the terminal shows the exact CLI
   invocation as visible text, in addition to the existing clipboard-copy
   attempt (unchanged).
2. **Given** the terminal/multiplexer does not support the clipboard escape
   sequence (the common failure case this feature addresses), **When** the
   user presses "Copy & exit", **Then** they can still retrieve the
   invocation by selecting the printed text with the terminal's own
   selection — no clipboard support is required.
3. **Given** the terminal *does* support the clipboard escape sequence,
   **When** the user presses "Copy & exit", **Then** the invocation is both
   on the clipboard and printed — the printed line is not treated as an
   error or a sign that the clipboard attempt failed, since the app has no
   reliable way to detect whether the clipboard attempt actually reached a
   real clipboard.
4. **Given** any per-command screen with a "Copy & exit" shortcut, **When**
   the user presses it, **Then** the behavior in Scenarios 1-3 applies —
   this is not limited to one specific command's screen.
5. **Given** a form with a required field still empty, **When** the user
   presses "Copy & exit", **Then** the printed invocation matches exactly
   what plain "Copy" would have placed on the clipboard for those same field
   values — unaffected by this feature, whether or not the invocation is
   complete.

### Edge Cases

- What happens if the user presses plain "Copy" (without exiting) and later
  exits via a different shortcut (e.g. Cancel)? Nothing is printed — the
  fallback only applies to the combined "Copy & exit" action, since the app
  is still running (in full-screen mode) after a plain "Copy", so anything
  printed to the terminal at that point would not be visible until the user
  eventually exits some other way, and would be disconnected from what
  triggered it.
- What happens on a terminal that *does* support the clipboard escape
  sequence? The invocation is printed every time regardless — the app
  cannot reliably detect whether a given terminal actually applied the
  clipboard write, so it never suppresses the printed fallback.
- What happens if "Copy & exit" is pressed on a screen whose fields produce
  an unusual or very long invocation (e.g. many `--voxel_size` values)? The
  full, unmodified invocation text is printed — no truncation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every per-command screen's "Copy & exit" shortcut MUST, after
  the application exits, print the exact CLI invocation string to the
  user's terminal — the identical string the existing clipboard-copy
  attempt uses.
- **FR-002**: The existing clipboard-copy attempt on "Copy & exit" MUST be
  preserved unchanged — this feature adds a fallback, it does not replace
  the clipboard attempt.
- **FR-003**: The printed invocation MUST appear in the user's normal
  terminal scrollback after the TUI's full-screen display has been torn
  down — not inside the TUI's own on-screen log, which disappears when the
  app exits.
- **FR-004**: This behavior MUST apply uniformly to every per-command
  screen that offers a "Copy & exit" shortcut, with no screen excluded.
- **FR-005**: The printed output MUST be clearly distinguishable from
  ordinary shell output (e.g. a short label identifying it as the copied
  invocation), and MUST reproduce the invocation text exactly — same
  tokens, same order, same quoting, as the clipboard-copy attempt.
- **FR-006**: Plain "Copy" (without exiting) MUST NOT be changed by this
  feature — it remains a clipboard-only attempt, since the app keeps
  running afterward.
- **FR-007**: The app MUST NOT attempt to detect or report whether the
  clipboard-copy attempt actually succeeded — printing the fallback MUST
  happen unconditionally on "Copy & exit", not only when a failure is
  detected, since there is no reliable way to detect clipboard delivery
  from inside the app.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After using "Copy & exit" on any per-command screen, the exact
  CLI invocation is visible in the user's terminal after the app exits,
  100% of the time — independent of the terminal's or multiplexer's
  clipboard support.
- **SC-002**: A user on a terminal/multiplexer without working clipboard
  passthrough can retrieve the invocation with zero additional
  configuration (no environment variables, no terminal settings changes).
- **SC-003**: Existing "Copy & exit" behavior for users on terminals with
  working clipboard support is unaffected — the invocation still ends up on
  the clipboard exactly as before.

## Assumptions

- **Scope is "Copy & exit" only, not plain "Copy"**: the feature description
  frames this specifically around exiting, since that's the only point at
  which the TUI's full-screen display is torn down and printed terminal
  output becomes visible; plain "Copy" leaves the app running, so there's no
  useful moment to print a fallback yet.
- **No new confirmation/preference required**: the printed fallback always
  appears on every "Copy & exit", with no way to disable it and no attempt
  to detect clipboard success first — keeping the behavior simple and
  eliminates any case where the fallback is silently skipped.
- **"Every per-command screen"**: covers all five places `action_copy_and_exit`
  exists today — the generic `CommandFormScreen`, `InspectScreen`,
  `fix_metadata`/`migrate`'s Form and Confirm screens (spec 004 User Story
  8), and `ConfigScreen`.
