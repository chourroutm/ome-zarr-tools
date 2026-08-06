# Feature Specification: Consistent TUI Menus & Forms

**Feature Branch**: `003-tui-menu-consistency`

**Created**: 2026-08-06

**Status**: Draft

**Input**: User description: "improve the menus and forms taking https://github.com/batrachianai/toad and other textual-based repos as examples. for from_images, remove the panel with the command preview. make all submenus consistent with the same sets of shortcuts and structures."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One shortcut set to learn, everywhere (Priority: P1)

A user opens the TUI (`interactive --tui`), picks a command from the menu, and
runs it. They then go back and pick a different command. The footer shows the
same shared shortcuts (Run/primary action, Copy, Copy & exit, Toggle log, Back,
Cancel), bound to the same keys, in the same order, on every command screen —
generic form screens (`from_images`, `extract`, `apply_mask`) and specialized
screens (`fix_metadata`, `migrate`, `inspect`, `config`) alike. Any
screen-specific extra shortcut (e.g. `inspect`'s panel switch) appears after
the shared set, never in place of it.

**Why this priority**: This is the core of "consistent menus and forms" — if
shortcuts move around or get relabeled per screen, the user has to re-learn
navigation every time they switch commands, which defeats the point of a
single interactive tool.

**Independent Test**: Open each of the seven command screens in turn and
compare the footer's key/label pairs for the shared actions; they must match
exactly in key and position across all seven.

**Acceptance Scenarios**:

1. **Given** the user is on any command screen, **When** they look at the
   footer, **Then** Run/primary-action, Copy, Copy & exit, Toggle log, Back,
   and Cancel appear bound to the same keys (F5–F8, Escape, Ctrl+C) in the
   same left-to-right order as every other command screen.
2. **Given** a screen's primary action has a more specific name than "Run"
   (e.g. `config`'s save action), **When** the user views the footer,
   **Then** the shortcut still occupies the same key and position, with only
   the displayed label adapted to the screen's verb (e.g. "Save" instead of
   "Run").
3. **Given** a screen has a shortcut with no equivalent on other screens
   (e.g. `inspect`'s panel switch), **When** the user views the footer,
   **Then** that shortcut appears after the full shared set, not interleaved
   with it.

---

### User Story 2 - Cleaner generic-form screens (Priority: P2)

A user opens `from_images` in the TUI to convert an image stack. Today, a live
"$ ome-zarr-tools from_images ..." line above the form re-renders on every
keystroke, taking up vertical space and duplicating what Copy/Copy & exit
already produce. The user wants that panel gone so the form itself is easier
to scan, while still being able to copy the exact equivalent command via the
existing Copy shortcuts. Since `from_images` shares its form screen with
`extract` and `apply_mask`, the same change applies to all three so the
shared screen stays visually consistent.

**Why this priority**: Directly requested; secondary to shortcut consistency
because it only affects the generic form screens' layout, not navigation.

**Independent Test**: Open each of `from_images`, `extract`, and
`apply_mask`, fill in fields, and confirm no live command-invocation line is
rendered anywhere on screen, while Copy and Copy & exit still place the
correct, fully up-to-date invocation on the clipboard.

**Acceptance Scenarios**:

1. **Given** the user is on the `from_images`, `extract`, or `apply_mask`
   form, **When** they edit any field, **Then** no command-preview line is
   shown or updated anywhere on the screen.
2. **Given** the user has filled in one of these forms, **When** they press
   Copy or Copy & exit, **Then** the clipboard receives the exact, correct
   CLI invocation for the current field values, even though it was never
   displayed.

---

### User Story 3 - Same structural skeleton across all screens (Priority: P3)

A user comparing `extract`, `fix_metadata`, and `inspect` notices they don't
look like different apps stitched together: each has the same header, a
scrollable field/content area, a status/log region docked at the bottom, and
a footer — just with different content in the middle for what that command
needs (a diff view for `fix_metadata`, JSON panels for `inspect`, a config
editor for `config`).

**Why this priority**: Reinforces the first two stories but is lower-impact
on its own — most of this structural consistency already exists; this story
mainly guards against future commands drifting from the pattern.

**Independent Test**: Open every command screen and confirm each has exactly
one header, one bottom-docked status/log region directly above the footer,
and one footer — with no screen adding a second competing bottom-docked
region or omitting the status/log area.

**Acceptance Scenarios**:

1. **Given** any command screen, **When** it is rendered, **Then** it shows
   exactly one header at the top and exactly one footer at the bottom, with a
   status/log region immediately above the footer.
2. **Given** a command screen has content specific to that command (form
   fields, a diff view, JSON panels, a config editor), **When** rendered,
   **Then** that content occupies the scrollable area between the header and
   the status/log region, without altering the shared header/status/footer
   skeleton.

### Edge Cases

- What happens on a command with no extra, screen-specific shortcuts beyond
  the shared set (e.g. `extract`)? The footer shows only the shared set —
  nothing is added, nothing is missing.
- What happens on a narrow terminal where not all footer shortcuts fit on one
  line? Existing footer overflow/truncation behavior is unchanged by this
  feature; shortcut *content and order* are what must stay consistent, not
  guaranteed on-screen fit at any width.
- What happens if a required field is empty when the user presses Copy or
  Copy & exit on `from_images`, `extract`, or `apply_mask` now that the
  preview is gone? The existing required-field validation (used today for
  Run) still applies — the clipboard must not receive an invocation missing
  a required value.

## Clarifications

### Session 2026-08-06

- Q: `from_images`, `extract`, and `apply_mask` currently share one generic
  form screen, so the command-preview panel is one shared piece of UI. Should
  the panel be removed only for `from_images`, or for all three commands
  that use the generic form screen? → A: Remove it for all three, keeping
  the generic form screen visually consistent across every command that
  uses it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every TUI command screen (the command menu, generic form
  screens, and specialized screens for `fix_metadata`, `migrate`, `inspect`,
  and `config`) MUST expose the shared shortcut set — primary action, Copy,
  Copy & exit, Toggle log, Back, Cancel — bound to the same keys, in the same
  order, in the footer.
- **FR-002**: Where a screen's primary action is more accurately described by
  a different verb than "Run" (e.g. `config`'s save action), the shortcut's
  displayed label MUST use that verb while keeping the same key binding and
  position as the shared "primary action" slot.
- **FR-003**: Any shortcut specific to a single screen (not part of the
  shared set) MUST be listed after the full shared set in the footer, never
  interleaved with shared shortcuts.
- **FR-004**: The generic form screen (used by `from_images`, `extract`, and
  `apply_mask`) MUST NOT display a live command-preview panel (the
  constructed "$ ome-zarr-tools \<command\> ..." line).
- **FR-005**: Removing the command-preview panel MUST NOT change what Copy
  and Copy & exit place on the clipboard — both MUST continue to produce the
  exact, current CLI invocation for the form's field values.
- **FR-006**: Existing required-field validation that blocks running a
  command with missing required fields MUST also block Copy and Copy & exit
  from producing an incomplete invocation.
- **FR-007**: Every command screen MUST follow the same structural skeleton:
  one header, one scrollable command-specific content area, one status/log
  region docked directly above the footer, and one footer.
- **FR-008**: The command menu screen MUST use the same header/footer chrome
  as every command screen, so entering and leaving a command doesn't change
  the overall window framing.

### Key Entities

- **Command Screen**: Any full-screen view in the TUI a user can be on —
  either the command menu or one specific command's screen (generic form or
  specialized). Has a header, a content area, a status/log region, and a
  footer.
- **Shared Shortcut Set**: The fixed list of (key, action, label-template)
  triples — primary action, Copy, Copy & exit, Toggle log, Back, Cancel —
  that every Command Screen must expose in the same key/order, with only the
  primary action's label allowed to vary per screen.
- **Command-Preview Panel**: The live, auto-updating line showing the
  equivalent direct-CLI invocation for the current form values. Removed for
  `from_images`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across all seven command screens, the shared shortcut set's
  keys and left-to-right footer order match exactly — 0 discrepancies.
- **SC-002**: The `from_images`, `extract`, and `apply_mask` screens render
  no command-preview text at any point during field entry, verified by
  screen inspection.
- **SC-003**: Copy and Copy & exit on `from_images`, `extract`, and
  `apply_mask` produce a clipboard value identical to what the removed
  preview line would have shown, for every combination of filled-in fields
  exercised in tests.
- **SC-004**: A user who has used any one command screen can identify the Run
  (or screen-appropriate primary action), Copy, and Back shortcuts on any
  other command screen without reading documentation, because the key and
  position never change.

## Assumptions

- "Submenus" refers to the per-command screens reached from the top-level
  command menu (generic form screens and the four specialized screens), not
  a deeper nested menu structure — none currently exists.
- The Toad-inspired improvement is scoped to shortcut/structure consistency
  and removing `from_images`'s command-preview panel, as explicitly
  requested; it does not include adopting unrelated Toad features (e.g. a
  dedicated all-keybindings help screen, fuzzy file pickers) that were not
  asked for.
- Textual's built-in `Footer` widget continues to be the mechanism for
  displaying shortcuts; no custom shortcut-rendering widget is introduced.
