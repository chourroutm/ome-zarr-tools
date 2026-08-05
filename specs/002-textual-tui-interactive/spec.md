# Feature Specification: Textual-Based TUI for Interactive Mode

**Feature Branch**: `002-textual-tui-interactive`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "keep the basic prompt-based interactive command, but also add a Textual-based interface to it. The Textual-based interface must also provide autocomplete for paths"

## Clarifications

### Session 2026-08-05

- Q: Now that the Run shortcut skips the old confirmation dialog, what should still happen before the command actually executes? → A: The equivalent CLI invocation is always visible in the status/log area before Run is pressed; pressing Run executes immediately with no additional prompt — the keypress itself is the confirmation.
- Q: When the user presses the "copy" shortcut, where should the equivalent command line go? → A: Try the terminal's OSC 52 clipboard-write sequence (real system clipboard) first; if the terminal/SSH session doesn't support it, fall back to showing the text selectably in the log panel instead of silently failing.
- Q: What exactly should count as a "conflict" that triggers the diff/rich-view editor in fix_metadata and migrate? → A: Always show a full diff of old vs. proposed metadata before writing, for every fix_metadata/migrate run, whether or not anything is actually contentious.
- Q: Should the TUI's config editor operate on the user-level config, the project-level config, or let the user pick? → A: Mirrors config's existing --user/--project distinction — the user picks scope, and the screen shows defaults and the merged effective view for whichever scope is selected.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep Using the Existing Prompt-Based Flow (Priority: P1)

A user who is already comfortable with `interactive`'s current line-by-line prompts (select a command from a numbered menu, answer one question at a time) continues to get exactly that experience by default. Nothing about today's behavior changes for them.

**Why this priority**: This is an explicit, non-negotiable constraint from the request ("keep the basic prompt-based interactive command"). Every other user story in this feature must not regress it.

**Independent Test**: Can be fully tested by running `interactive` the same way it's run today and confirming the menu, per-command wizards, cancellation behavior, and equivalent-command-line output are byte-for-byte the same as before this feature.

**Acceptance Scenarios**:

1. **Given** a user runs `interactive` without requesting the new full-screen mode, **When** the session starts, **Then** they see the existing numbered, line-by-line menu and prompts exactly as before.
2. **Given** the user completes the prompt-based flow, **When** they confirm, **Then** the selected command runs exactly as it does today.

---

### User Story 2 - Navigate a Full-Screen Terminal UI With Keyboard Shortcuts, Not Buttons (Priority: P1)

A user launches the new full-screen terminal interface (built with the Textual framework) and, instead of answering prompts one line at a time or clicking a button, sees a persistent screen with a menu of commands and a form of fields for the selected command's options — fields they can tab between, edit, and review together. A persistent footer shows the available keyboard shortcuts: **Run** (execute now), **Copy** (copy the equivalent command line without running it), and **Copy-and-exit** (copy, then close the interface). There is no confirmation dialog to click through — the equivalent command line is always visible before Run is pressed, and pressing it runs immediately.

**Why this priority**: This is the other explicit, named requirement of the request ("add a Textual-based interface to it") and is the feature's primary new value: a more discoverable, reviewable, keyboard-driven way to build and run a command.

**Independent Test**: Can be fully tested by launching the full-screen interface, selecting each available command in turn, filling in its form, and using each footer shortcut (Run, Copy, Copy-and-exit) to confirm it does exactly what its name says, matching what the equivalent direct CLI invocation or the prompt-based wizard would do.

**Acceptance Scenarios**:

1. **Given** a user requests the full-screen interface, **When** it opens, **Then** they see a menu of the same commands the prompt-based flow offers, without needing to scroll back through prior output to see their choices.
2. **Given** the user selects a command, **When** the form for that command's options appears, **Then** they can move between fields, see each field's current value and default, and edit any field — with the footer always showing the Run / Copy / Copy-and-exit shortcuts and the equivalent CLI invocation visible in the status/log area, updated live as fields change.
3. **Given** the user has filled in the form, **When** they press the Run shortcut, **Then** the command executes immediately — no modal or confirmation prompt appears, because the invocation was already visible before the keypress.
4. **Given** the user has filled in the form, **When** they press the Copy shortcut, **Then** the equivalent command line is copied (to the OS clipboard if the terminal supports it, otherwise shown selectably in the log) and nothing runs.
5. **Given** the user has filled in the form, **When** they press Copy-and-exit, **Then** the same copy happens and the full-screen interface closes without running anything.
6. **Given** the user wants to stop without using Copy, **When** they cancel or quit the interface at any point before pressing Run, **Then** no command runs and no side effects occur.
7. **Given** the full-screen interface cannot start (no interactive terminal available, e.g. output is piped or redirected), **When** the user requests it, **Then** the tool reports why clearly and does not crash.

---

### User Story 3 - Get Path Suggestions While Typing (Priority: P1)

While filling in a field that expects a filesystem path (a dataset location, an input directory, an output file), the user sees matching files and directories suggested as they type, instead of having to know or memorize the exact path in advance.

**Why this priority**: Explicitly required ("must also provide autocomplete for paths") and is what makes the full-screen interface meaningfully easier to use than typing a path blind — without it, User Story 2 is just a different-looking way to make the same typos.

**Independent Test**: Can be fully tested by focusing a path field in the full-screen interface, typing a partial path, and confirming the suggested completions match what actually exists on disk at that location; selecting a suggestion fills the field with the full path.

**Acceptance Scenarios**:

1. **Given** a path-type field is focused, **When** the user types a partial directory or file name, **Then** matching entries from that location are suggested.
2. **Given** suggestions are shown, **When** the user selects one, **Then** the field is filled with the selected path and the user can continue editing or move to the next field.
3. **Given** the typed partial path doesn't match anything on disk, **When** no suggestions are available, **Then** the field simply shows no suggestions rather than an error, and the user can still type a path manually (e.g. for a not-yet-created output file).

---

### User Story 4 - Review a Diff Before fix_metadata or migrate Writes Anything (Priority: P1)

Because `fix_metadata` and `migrate` overwrite a dataset's existing metadata, a user filling in either command's form always sees a full before/after diff of the metadata, plus a rich, structured view of the proposed result, before that command's Run shortcut writes anything. For `fix_metadata`, that structured view is directly editable (replacing the old one-field-at-a-time prompting with a single view of the whole proposed metadata). For `migrate`, it's a formatted preview of what the target version's metadata and storage will look like.

**Why this priority**: These are the two commands in the whole tool that overwrite a dataset's existing metadata. Now that Run no longer goes through a separate confirmation dialog (User Story 2), the diff/rich view is what carries that safety guarantee forward specifically for the two commands where getting it wrong is costliest — it is not optional the way it might be for lower-stakes commands.

**Independent Test**: Can be fully tested by opening `fix_metadata` or `migrate`'s form in the full-screen interface, changing the proposed values, and confirming a diff of old vs. new metadata is visible before Run is pressed — for every run, not just when something looks contentious.

**Acceptance Scenarios**:

1. **Given** the user opens `fix_metadata`'s form for a dataset with existing metadata, **When** the form loads, **Then** a diff view compares the current metadata against the proposed metadata, and a rich, directly editable view of the proposed metadata is shown alongside it.
2. **Given** the user opens `migrate`'s form, **When** a target version is chosen, **Then** a diff view compares the dataset's current metadata/storage description against what the migration would produce, shown as a formatted preview.
3. **Given** a dataset with no prior metadata at all, **When** `fix_metadata`'s form loads, **Then** the diff shows an empty "before" state and the full proposed metadata as "after" — the diff view is never skipped.
4. **Given** the user edits a value in `fix_metadata`'s rich view in a way that would fail validation (e.g. wrong type for a field), **When** the edit is made, **Then** the rich view flags the problem before Run can be pressed, using the same validation the direct CLI already enforces.
5. **Given** the diff/rich view has been shown, **When** the user presses Run, **Then** the command executes immediately with no further confirmation step — consistent with every other command's Run shortcut (User Story 2).

---

### User Story 5 - See Live Status While a Command Runs (Priority: P2)

While a command runs from the full-screen interface, the user sees a live status indicator — a progress bar when the command's work has a countable total (e.g. pyramid levels or chunks to write), or an animated sparkline when it doesn't — plus access to a log of the command's output, which stays out of the way until the user asks for it with a keyboard shortcut.

**Why this priority**: Valuable feedback for longer-running commands (`from_images`, `apply_mask`, `migrate`, `extract`), but the interface is already fully usable without it (today's plain-text `click.echo` output still appears); it's a quality-of-life layer on top of User Stories 2–4, not a blocker for them.

**Independent Test**: Can be fully tested by running a command from the full-screen interface and confirming a status indicator appears while it's in progress (matching progress-bar-vs-sparkline to whether that command's work is quantifiable) and that the log can be shown and hidden with a keyboard shortcut without interrupting the running command.

**Acceptance Scenarios**:

1. **Given** a command with a countable amount of work is running, **When** the user watches the status area, **Then** a progress bar reflects how much of that work is complete.
2. **Given** a command whose amount of work isn't known in advance, **When** it's running, **Then** an animated sparkline indicates activity without claiming a specific percentage complete.
3. **Given** a command is running or has just finished, **When** the user presses the log-toggle shortcut, **Then** the log becomes visible (or hides again on a second press) without interrupting or restarting the command.
4. **Given** a command's work becomes countable only partway through (e.g. after scanning a directory to find how many files exist), **When** that happens, **Then** the status indicator may switch from a sparkline to a progress bar at that point.

---

### User Story 6 - Browse a Dataset's Structure Through Rich Inspect Panels (Priority: P2)

Running `inspect` from the full-screen interface shows its report as more than one flat block of text: a scrollable, syntax-highlighted JSON panel for each resolution level's metadata, and a separate summary panel of the dataset's overall structure (levels, shapes, chunk/shard layout, sizes) — the same information the CLI's `inspect --format json`/text output already contains, presented for browsing rather than printed once and scrolled past.

**Why this priority**: A meaningful upgrade to a read-only, already-working command; valuable but not on the critical path the way the diff view (User Story 4) or basic navigation (User Story 2) are.

**Independent Test**: Can be fully tested by running `inspect` from the full-screen interface against a known dataset and confirming the JSON panel's content for each level matches the CLI's own JSON output, and the summary panel's figures (shapes, sizes) match too.

**Acceptance Scenarios**:

1. **Given** `inspect`'s form is submitted (or run) for a valid dataset, **When** results are shown, **Then** a panel presents the full, scrollable JSON metadata for each resolution level.
2. **Given** the same results, **When** the user views the summary panel, **Then** it shows the dataset's overall structure (per-level shapes, chunk/shard layout, stored/logical sizes, total sizes) without requiring the JSON panel to be read to find it.
3. **Given** both panels exist, **When** the user wants to move between them, **Then** a keyboard shortcut switches focus/view between the JSON panel and the summary panel.

---

### User Story 7 - Edit Configuration in a Rich JSON Editor (Priority: P2)

Running `config` from the full-screen interface shows, for a scope the user selects (user-level or project-level, matching the CLI's existing `--user`/`--project` distinction), the currently effective preferences, the tool's built-in default values for comparison, and a rich, editable JSON editor for the underlying config file itself — rather than the CLI's current `show`/`set`/`reset` subcommands typed out separately.

**Why this priority**: Configuration is infrequent, low-risk (no dataset data at stake), and already fully usable via the CLI's `config` subcommands; this is a convenience upgrade, not something blocking any other story.

**Independent Test**: Can be fully tested by opening `config`'s screen in the full-screen interface, switching between user and project scope, confirming the shown "current" values match what `config show` would report and the shown defaults match the CLI's documented option defaults, editing the JSON, and confirming the write matches what `config set` would have produced.

**Acceptance Scenarios**:

1. **Given** the user opens the config screen, **When** it loads, **Then** they can pick user-scope or project-scope, and see that scope's current effective values alongside the tool's built-in defaults.
2. **Given** a scope is selected, **When** the user edits the config JSON directly in the rich editor, **Then** the edit is validated as JSON before it can be saved.
3. **Given** invalid JSON is entered, **When** the user tries to save, **Then** the editor flags the syntax problem and blocks the write without discarding the user's in-progress edit.

---

### Edge Cases

- What happens when the user resizes the terminal while the full-screen interface is open?
- How does the full-screen interface behave for a command whose options include one the prompt-based wizard already handles specially (e.g. a flag, or a repeatable option like `from_images`'s `--voxel_size`)?
- How does path autocomplete behave for a path that doesn't exist yet (e.g. `from_images`'s output location, which must not already exist)?
- How does the full-screen interface behave if the terminal window is too small to show the current form?
- What happens if the user's answers in a *generic* command's form (i.e. not `fix_metadata`) would fail validation the direct CLI enforces beyond a required field being empty (e.g. `extract`'s two mutually exclusive crop options both filled in)? Only required-field-non-empty is checked before Run (FR-004); other validation is not re-implemented in the TUI and instead surfaces the same way any other command failure does — the command runs, the CLI raises its usual error, and that error is caught and shown as a failed result in the log (User Story 5) rather than blocking Run proactively. Proactive, before-Run flagging of invalid values is specific to `fix_metadata`'s rich view (FR-018, User Story 4), which replaces field-by-field prompting with structured editing precisely because that command's edits need it; extending the same proactive check to every command's arbitrary CLI-level validation is out of scope for this feature.
- What happens if the Copy shortcut's OS clipboard attempt (OSC 52) isn't supported by the current terminal/SSH session? It falls back to showing the command line selectably in the log panel rather than failing silently.
- What happens if the user toggles the log open while a status indicator (progress bar or sparkline) is active? Both remain visible/available together; toggling the log doesn't pause or restart the running command.
- How does the diff view behave for a dataset with no prior metadata at all? The "before" side is shown empty rather than the diff being skipped (User Story 4, Acceptance Scenario 3).
- What happens if the user edits config JSON to something that parses but fails the config file's own semantics (not just malformed JSON)? The same validation `config set` already applies is enforced before writing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `interactive` command MUST continue to offer its existing line-by-line, prompt-based menu and per-command wizards exactly as they behave today, unchanged.
- **FR-002**: The `interactive` command MUST offer a full-screen terminal interface, built with the Textual framework, as an alternative to the prompt-based flow.
- **FR-003**: The full-screen interface MUST present the same set of commands as the prompt-based menu, kept in sync automatically as commands are added or removed (matching today's behavior of introspecting whatever is registered).
- **FR-004**: The full-screen interface MUST let the user review and edit all of a selected command's field values together, rather than one at a time with no way back.
- **FR-005**: The full-screen interface MUST NOT use a button to run a command. Instead, it MUST expose **Run**, **Copy**, and **Copy-and-exit** as keyboard shortcuts displayed in a persistent footer. Run MUST execute the command on that single keypress with no separate confirmation dialog; the equivalent direct-CLI invocation MUST already be visible (in the status/log area) at the time Run is pressed, so the keypress itself — with the command already visible — is what stands in for the old confirmation step.
- **FR-006**: The Copy shortcut MUST copy the equivalent command line without running anything. It MUST attempt to write to the OS clipboard via the terminal's OSC 52 sequence first; if that isn't supported by the current terminal/SSH session, it MUST fall back to presenting the command line selectably within the log panel rather than failing silently.
- **FR-007**: The Copy-and-exit shortcut MUST perform the same copy as FR-006 and then close the full-screen interface without running anything.
- **FR-008**: Any field in the full-screen interface that corresponds to a filesystem path MUST offer autocomplete suggestions drawn from the actual filesystem as the user types.
- **FR-009**: Path autocomplete MUST tolerate a partial path that matches nothing (no existing file/directory) without blocking the user from continuing to type a path manually — needed for fields that name a not-yet-created output location.
- **FR-010**: When the full-screen interface cannot be started (e.g. no interactive terminal is attached), the tool MUST report a clear message and MUST NOT crash; the prompt-based flow remains available as a fallback.
- **FR-011**: The full-screen interface MUST be reached via an explicit flag on `interactive` (e.g. `interactive --tui`); omitting the flag MUST continue to launch the existing prompt-based flow, unchanged. This MUST be documented alongside the default invocation.
- **FR-012**: The package MUST include automated tests covering the full-screen interface's command menu, field editing, path autocomplete, the Run/Copy/Copy-and-exit shortcuts, the status indicator, the log toggle, the fix_metadata/migrate diff view, the inspect panels, the config editor, and cancellation — consistent with this project's existing practice of a success path and a failure path per capability.
- **FR-013**: Path autocomplete MUST be presented as an inline, type-ahead suggestion list that filters live, within the path field itself, as the user types — not a separate file-browser screen or dialog.
- **FR-014**: While a command runs from the full-screen interface, the interface MUST show a live status indicator: a progress bar when the command's remaining work has a countable total, otherwise an animated sparkline indicating activity without a numeric target.
- **FR-015**: A log of the running (or just-run) command's output MUST be available from the full-screen interface and toggleable via a keyboard shortcut, hidden by default so it doesn't permanently consume screen space.
- **FR-016**: Running `inspect` from the full-screen interface MUST present its results as, at minimum: a scrollable, syntax-highlighted JSON panel per resolution level, and a separate summary panel of the dataset's overall structure (per-level shapes, chunk/shard layout, sizes, totals) — both switchable via keyboard shortcut, covering the same content the CLI's `inspect` output already provides.
- **FR-017**: Running `config` from the full-screen interface MUST let the user pick user-scope or project-scope (matching the CLI's `--user`/`--project` distinction) and, for the selected scope, show the currently effective preferences, the tool's built-in default values, and a rich, editable JSON editor for the underlying config file — writes going through the same validation `config set` already performs.
- **FR-018**: `fix_metadata` and `migrate`'s forms in the full-screen interface MUST always show, before Run can meaningfully act, a diff of the dataset's current metadata against the proposed metadata, and a rich structured view of the proposed result — every run, not only when something looks contentious. For `fix_metadata`, this rich view MUST be directly editable, replacing one-field-at-a-time prompting with a single structured view of the whole proposed metadata; edits that would fail the CLI's own validation MUST be flagged in the view before Run can be pressed. For `migrate`, this rich view is a formatted preview of the target version's result.
- **FR-019**: For `fix_metadata` and `migrate`, the diff/rich view required by FR-018 is what satisfies FR-005's "visible before Run" requirement — Run still executes on a single keypress once the diff/view has been shown, with no separate modal confirmation, consistent with every other command.

### Key Entities

- **TUI Session**: The full-screen interface's in-memory state for one run — which command is selected, the current value of each of its fields, the live equivalent-invocation text, status/log state, and whether the user has run, copied, cancelled, or is still editing.
- **Path Suggestion List**: The set of filesystem entries offered for a given path field at a given moment, derived from whatever the user has typed so far.
- **Status Indicator**: The live representation of a running command's progress — either a quantified progress bar (a known current/total) or an indeterminate animated sparkline (activity without a numeric target) — shown while a command executes.
- **Command Log**: The scrollable record of a running or just-run command's output; hidden by default, toggled via keyboard shortcut, independent of the status indicator.
- **Diff View**: The before/after comparison of a dataset's metadata shown for every `fix_metadata`/`migrate` run, prior to Run being pressed.
- **Rich View/Edit Surface**: The structured (tree/JSON) presentation of a command's proposed result — directly editable for `fix_metadata`'s proposed metadata; a formatted preview for `migrate`'s target-version result; the JSON-per-level and summary panels for `inspect`'s results; and the config file editor for `config`.
- **Config Editor**: The rich JSON editor for a config file at a chosen scope (user or project), shown alongside that scope's current effective values and the tool's built-in defaults.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every acceptance scenario and behavior available in `interactive` before this feature continues to pass unchanged (zero regressions to the prompt-based flow).
- **SC-002**: A user can go from launching the full-screen interface to a running command without typing a full path from memory for any path-type field — autocomplete surfaces it after a few keystrokes.
- **SC-003**: A user who starts filling in a command's form in the full-screen interface and changes their mind about an earlier field can correct it without restarting the whole form, unlike the strictly sequential prompt-based flow.
- **SC-004**: Attempting to launch the full-screen interface in an environment that can't support it produces a clear, non-crashing message 100% of the time in the automated test suite.
- **SC-005**: A user can copy a fully-built command line without running it, in one keypress, without any additional screen or dialog — whether or not the terminal supports OS-clipboard integration.
- **SC-006**: 100% of `fix_metadata` and `migrate` runs from the full-screen interface show a before/after diff of the dataset's metadata before anything is written — verified in the automated test suite across both a no-prior-metadata case and an existing-metadata case.
- **SC-007**: A user can determine a dataset's full per-level metadata and overall structure from `inspect`'s panels without leaving the full-screen interface or reading the plain-text CLI report.
- **SC-008**: A user can view and edit both user-scope and project-scope configuration, including comparing current values against built-in defaults, without leaving the full-screen interface.

## Assumptions

- Path autocomplete operates against the local filesystem; remote/cloud paths (the tool's `cloudpathlib`-backed remote store support) are out of scope for autocomplete in this feature and can still be typed manually.
- The full-screen interface covers the same set of commands the prompt-based menu covers today; it does not need to expose any capability the prompt-based flow doesn't already have.
- "Textual" refers to the open-source Python TUI framework of that name; this is an explicit, named requirement from the user rather than a technology choice left to the planning phase.
- `inspect`'s JSON panel and structure-summary panel (User Story 6) are switchable/tabbed views within the same screen rather than always-simultaneous side-by-side panes, to stay usable in modest terminal sizes; the planning phase may revisit this if terminal width assumptions change.
- Whether a given command's status indicator (User Story 5) is a progress bar or a sparkline is chosen per-command, based on whether that command's underlying work has a countable total at the time it starts (e.g. pyramid levels for `from_images`, chunks for `apply_mask`); the exact per-command mapping is a planning-phase detail, not enumerated in this spec.
- For `migrate`, the rich view/edit surface (FR-018) defaults to a read-only formatted preview; it may also allow direct edits before Run for consistency with `fix_metadata`, but `migrate`'s normal flow doesn't require manual editing to complete successfully.
- Exact footer shortcut keys (which key runs, which copies, which toggles the log, etc.) are a planning-phase decision, not enumerated in this spec, as long as they remain discoverable via the persistent footer (FR-005) and don't conflict with existing navigation (Tab/Escape/Ctrl+C, established in this feature's original scope).
- Config's "default preferences" (User Story 7, FR-017) means the tool's built-in option defaults (e.g. `--threshold 0.5`) shown for comparison — not a separate third config-file tier.
- Proactive, before-Run validation beyond "required field filled" (FR-004) is scoped to `fix_metadata`'s rich view only (FR-018/User Story 4) — see the corresponding Edge Case. Every other command's other CLI-level validation (e.g. mutually exclusive options) surfaces after Run, as a failed result in the log (User Story 5), the same as any other command failure; this feature does not add a generic pre-Run validation layer for every command.
