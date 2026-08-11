# Feature Specification: TUI Visual Redesign

**Feature Branch**: `004-tui-visual-redesign`

**Created**: 2026-08-06

**Status**: Draft

**Input**: User description: "the TUI is ugly, I want to pimp it a bit. Like in Toad, add a logo at the top; that logo can be Matriochka doll inspired in ASCII. In forms, reorder the fields whether they are required or optional, add frame boxes and edit case (the current case matches the CLI conventions, but that is not pretty). Also look at the Dolphie and Harlequin examples: https://textual.textualize.io/"

## Clarifications

### Session 2026-08-06

- Q: When a field label is too long to fit the frame's width, should it wrap to a second line or truncate with an ellipsis? → A: Wrap to multiple lines — never hides label text, safer for a data-entry form than the compact single-line Toad/Dolphie aesthetic invoked elsewhere.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A distinctive first impression (Priority: P1)

A user opens `interactive --tui` and, before anything else, sees a
hand-crafted logo above the command menu — three filled, bottom-aligned
squares of decreasing size (4×4, 3×3, 2×2) side by side, one in each of
OME's three brand colors (red, green, blue), echoing the size progression
of a nested set while reading cleanly at a glance. Below it, the command
list itself is made up of
larger, more prominent rows — echoing Toad's model-picker list — instead of
today's compact, single-line `OptionList` entries. The app immediately reads
as a designed tool with its own identity, not a generic list of subcommands
in a box. The logo and enlarged rows are specific to the command menu —
every other screen (forms, `inspect`, `config`, `fix_metadata`/`migrate`) is
out of scope for those two changes.

**Why this priority**: The single most requested, highest-visibility change
("add a logo at the top... like in Toad") — it's the first thing every user
sees, every time.

**Independent Test**: Open the command menu at a standard terminal size
(80×24 or larger) and confirm the ASCII logo renders above the command list,
and that each command occupies a 3-line highlightable block rather than
today's 1-line highlightable text.

**Acceptance Scenarios**:

1. **Given** the user opens `interactive --tui`, **When** the command menu
   appears, **Then** the ASCII logo is shown above the command list.
2. **Given** a terminal too narrow or short to fit the logo without pushing
   the command list off screen, **When** the menu renders, **Then** the logo
   is hidden rather than clipping or corrupting the layout.
3. **Given** the command menu is shown, **When** the user views the command
   list, **Then** each entry is a 3-line highlightable block (up from
   today's 1-line highlightable text), with selection/highlight behavior
   unchanged (arrow keys/click still select; Enter still opens that
   command's screen).

---

### User Story 2 - Forms that look designed, not dumped (Priority: P2)

A user opens any command's form (`from_images`, `extract`, `apply_mask`, or
the specialized `fix_metadata`/`migrate`/`inspect`/`config` screens) and
sees required fields grouped together, ahead of optional fields, each group
inside its own titled, bordered frame — instead of today's single
undifferentiated, unframed list in whatever order Click happened to declare
the parameters. The required-fields frame uses a solid red border, the
optional-fields frame a solid blue border, so the two groups are
distinguishable at a glance even before reading either title. The
required-fields frame's subtitle also tells the user, at all times, how
many of its fields are still empty — so they can tell they're done without
scanning the whole frame.

**Why this priority**: The second most concrete ask, and the highest-traffic
screens in the app (every command's data-entry surface); framed,
grouped forms are the core of "reorder the fields... add frame boxes."
Informed by Harlequin and Dolphie's shared use of clean, titled, bordered
panels to organize dense information without clutter.

**Independent Test**: Open a form with a mix of required and optional
fields (e.g. `from_images`); confirm all required fields appear inside one
red-bordered frame, ahead of all optional fields in a second blue-bordered
frame, and that the required frame's subtitle shows the correct
still-empty count as fields are filled in.

**Acceptance Scenarios**:

1. **Given** a command form with both required and optional fields,
   **When** it renders, **Then** required fields appear together in one
   tall-red-bordered, titled frame, positioned before a second
   tall-blue-bordered, titled frame containing the optional fields.
2. **Given** a command form with only required fields (or only optional
   fields), **When** it renders, **Then** only the one relevant frame is
   shown — no empty frame for the other group.
3. **Given** the required-fields frame is shown, **When** the user views its
   border subtitle, **Then** it states how many required fields are still
   empty (e.g. "2 remaining"), and that count updates as the user fills in
   or clears required fields.
4. **Given** every required field has a value, **When** the user views the
   required frame's subtitle, **Then** it reflects zero fields remaining
   (e.g. "0 remaining") rather than being removed or left stale.
5. **Given** the user submits the form (Run/Copy/Copy & exit), **When** the
   resulting CLI invocation is built, **Then** it is identical to what the
   pre-redesign field order would have produced — visual grouping does not
   change the underlying command.

---

### User Story 3 - Field labels people can read (Priority: P3)

A user looking at a form sees "Voxel Size Unit" and "Stack Dir", not
`--voxel_size_unit` and `--stack_dir`. The label reads like a sentence, not
a CLI flag, while the actual flag/argument the tool sends to the command
underneath is completely unchanged.

**Why this priority**: Lowest priority — it's a labeling/text change, not a
structural one, and the user themselves called it out as the smallest of
the three asks ("current case matches the CLI conventions, but that is not
pretty").

**Independent Test**: Open any form and confirm every field label reads as
capitalized words separated by spaces, with no leading dashes or
underscores, while the field's generated CLI token (checked via Copy) still
uses the original flag/argument name.

**Acceptance Scenarios**:

1. **Given** any command form, **When** it renders, **Then** every field
   label is shown as capitalized, space-separated words (e.g. "Voxel Size
   Unit") instead of the raw CLI flag/argument name (e.g. `--voxel_size_unit`).
2. **Given** a required field's label now reads in this human-readable
   form, **When** the user views it, **Then** the label carries no
   per-field required marker — required-ness is conveyed by the
   "Required" field-group frame it's grouped under (User Story 2),
   not by decorating the label itself.
3. **Given** the user fills in a relabeled field and copies the invocation,
   **When** they inspect the clipboard content, **Then** it uses the
   original CLI flag/argument name, unaffected by the label's display case.

---

### User Story 4 - Pick zarr paths without typing them (Priority: P4)

A user filling in any path field (`zarr_path`, `stack_dir`, `output_zarr`,
`mask`, `volume`, and similar) sees a 3-row "Browse" button to the right of
that field's input. Pressing it opens a directory-tree view of the local
filesystem; navigating and selecting an entry fills the field with that
path and returns to the form. Typing (with the existing path autocomplete)
remains available exactly as before — Browse is an additional way in, not a
replacement.

**Why this priority**: Least urgent of the four requested changes — path
fields are already usable today via typing plus autocomplete; this makes
them faster to fill without fixing something broken.

**Independent Test**: Open a form with a path field (e.g. `inspect`'s
`zarr_path`); confirm a "Browse" button appears to its right; press it,
navigate the resulting directory-tree view, select an entry, and confirm
the field is filled with that path and the form is otherwise unchanged.

**Acceptance Scenarios**:

1. **Given** a form with a path-typed field, **When** it renders, **Then**
   a 3-row "Browse" button appears to the right of that field's input.
2. **Given** the user presses Browse, **When** the directory-tree view
   opens, **Then** it starts from the field's current value's parent
   directory if set, otherwise the current working directory — the same
   rooting rule the existing path autocomplete already uses.
3. **Given** the user selects an entry in the directory-tree view, **When**
   selection completes, **Then** the corresponding field is filled with
   that path and the view closes back to the form, with every other
   field's value unchanged.
4. **Given** the user opens the directory-tree view and dismisses it
   without selecting anything, **When** they return to the form, **Then**
   the field's value is unchanged.
5. **Given** a field that only accepts a directory (or only a file),
   **When** the directory-tree view is open, **Then** only entries
   matching that constraint are selectable.
6. **Given** the directory-tree view is open, **When** the user edits the
   pre-filled path field above the tree and submits a different, valid
   directory, **Then** the view re-roots at that directory, making
   entries previously outside the tree entirely (an ancestor, a sibling,
   or any other reachable directory) reachable.
7. **Given** the user submits a value in that path field that is not a
   valid directory, **When** submission completes, **Then** the view
   shows an error and the root is left unchanged.

---

### User Story 5 - See remote paths as remote, not raw text (Priority: P5)

A user typing or pasting a remote path into a path field — any of the
schemes this tool already accepts (`gs://`, `gcs://`, `s3://`, `az://`,
`abfs://`, `http://`, `https://`) — sees the scheme rendered as a distinct,
colored, non-editable add-on to the left of the input, colored by provider:
blue for Google Cloud Storage (`gs://`/`gcs://`), orange for AWS S3
(`s3://`), cyan for Azure (`az://`/`abfs://`), and a neutral gray for the
provider-agnostic `http://`/`https://`. Only the remainder of the path
(bucket, key, filename) is editable inside the input itself.
Local-filesystem path autocomplete is disabled while a field is in this
state, since it has nothing useful to suggest for a remote path. If the
user deletes their way back to nothing in the editable portion, the scheme
prefix reappears as ordinary editable text in the input, so they can delete
it too and return to a plain field.

**Why this priority**: A precise, valuable usability detail for remote-path
entry (already a supported workflow), but narrower in scope than the
structural/visual changes in User Stories 1-4.

**Independent Test**: Type `gs://my-bucket/data.zarr` into a path field;
confirm a blue `gs://` add-on appears with `my-bucket/data.zarr` as the
only editable text, and no local-path autocomplete suggestions appear.
Repeat with `s3://` (orange), `az://`/`abfs://` (cyan), and `http://`/
`https://` (gray). Delete all the editable text after any add-on and
confirm the scheme reappears as plain editable text in the input.

**Acceptance Scenarios**:

1. **Given** a path field, **When** the user types or pastes a value
   starting with one of the recognized remote schemes followed by
   additional text, **Then** the field shows that scheme as a non-editable
   add-on, colored by provider (blue: `gs://`/`gcs://`; orange: `s3://`;
   cyan: `az://`/`abfs://`; gray: `http://`/`https://`), to the left of the
   input, with only the text after the scheme editable inside it.
2. **Given** a field in any add-on state, **When** the user views or
   interacts with it, **Then** no local-filesystem autocomplete suggestions
   are offered.
3. **Given** a field in any add-on state, **When** the user deletes all the
   editable text after the add-on (down to nothing), **Then** the scheme
   prefix reappears as ordinary, editable text inside the input, and the
   add-on is removed.
4. **Given** the scheme has reappeared as plain editable text (Acceptance
   Scenario 3), **When** the user continues deleting characters, **Then**
   they can delete the scheme itself, character by character, same as any
   other text.
5. **Given** a field with a Browse button (User Story 4), **When** the
   field is in any add-on state, **Then** the Browse button remains to the
   right of the whole input group, unaffected.

---

### User Story 6 - Know what you're about to run (Priority: P6)

A user opens any command's prep screen and sees, before any fields, a
titled, bordered frame stating the command's name and its existing CLI
description — the same identity already shown in the command menu — so
they always have a clear, at-a-glance confirmation of which command they're
configuring, even after scrolling past the header.

**Why this priority**: Continues the "designed, not dumped" per-screen
framing already established for field groups (User Story 2), applied to a
piece of identity most useful at the very top of every form. Lower
priority than the field frames themselves since it's a smaller, purely
additive piece of chrome.

**Independent Test**: Open any command's prep screen (generic or
specialized) and confirm a titled frame at the top shows the command's
name and description, sourced from the same text as its menu entry.

**Acceptance Scenarios**:

1. **Given** any command's prep screen, **When** it renders, **Then** a
   block appears above the field content showing the command's name in
   bold and its existing CLI description text underneath, with no border
   or title.
2. **Given** a command with no CLI help text, **When** its prep screen
   renders, **Then** the block still shows the command name, with the
   description area rendering blank rather than an error (same precedent
   as FR-002c).
3. **Given** the command-identity block and the required/optional
   field-group frames (User Story 2) are both shown on the same screen,
   **When** the user views it, **Then** the identity block is visually
   distinguishable from the field-group frames (borderless vs. solid
   red/solid blue borders), so the different content types don't blur
   together.

---

### User Story 7 - A dedicated place to see what happened (Priority: P7)

A user fills in a command's prep screen and presses Run. The app
immediately takes them to that command's dedicated Command Result screen
— it doesn't wait for the command to finish first. The Result screen
opens showing the same command-identity frame (name + description) as the
prep screen it came from, and, while the command is still running, a
progress bar (once progress is quantifiable) or an animated sparkline
(while it isn't yet) in place of the final content — the same status
indicator this app already shows elsewhere, just relocated here. Once
execution finishes — success or failure — that same screen swaps the
progress indicator for the outcome: a clear success/failure indicator,
the execution log, and that command's own specific output: `inspect`
shows its summary/JSON report, `fix_metadata`/`migrate` show the diff
that was applied, `config` shows the resulting config JSON, and every
other command shows its captured execution output/log. From the Result
screen, a clearly labeled shortcut takes the user back to that command's
prep screen with its field values exactly as they were before Run.
Separately, the prep screen itself gains a Restore Defaults shortcut that
resets every field back to the values it opened with, for a clean restart
without leaving the screen — achieved by reloading the prep screen itself
rather than resetting each field individually.

**Why this priority**: The least visually-driven of the new stories — it
changes navigation/screen architecture, not just appearance — so it's
sequenced after the purely visual stories.

**Independent Test**: Run any command and confirm the app navigates to
its Result screen immediately, showing a progress indicator; once the
command finishes, confirm that same screen shows a success indicator and
that command's specific output (or a failure indicator and the error, for
a failing invocation). Separately, confirm a prep screen's Restore
Defaults shortcut resets every field, and that a required field left
empty still blocks Run without navigating anywhere.

**Acceptance Scenarios**:

1. **Given** a command's prep screen with all required fields filled,
   **When** the user presses Run, **Then** the app immediately navigates
   to that command's Result screen, which shows the command-identity
   frame and a progress indicator (bar or sparkline) rather than waiting
   for the command to finish before navigating.
2. **Given** the Result screen is showing its progress indicator, **When**
   the command finishes successfully, **Then** the progress indicator is
   replaced by a success indicator, the execution log, and the command's
   specific output.
3. **Given** the same setup, **When** the command fails instead, **Then**
   the progress indicator is replaced by a failure indicator and the
   error message.
4. **Given** a prep screen where a required field is empty, **When** the
   user presses Run, **Then** the app does not navigate anywhere — the
   existing inline "field is required" notification is unchanged, since
   the command never actually executed.
5. **Given** the Result screen for any command, in either the pending or
   finished state, **When** the user triggers its return shortcut, **Then**
   the app goes back to that command's prep screen with its field values
   exactly as they were before Run.
6. **Given** `inspect`'s Result screen once finished, **When** it renders,
   **Then** it shows the same summary/JSON report panels the command
   already produces.
7. **Given** `fix_metadata`'s or `migrate`'s Result screen once finished,
   **When** it renders, **Then** it shows the diff that was actually
   applied.
8. **Given** `config`'s Result screen once finished, **When** it renders,
   **Then** it shows the resulting config JSON that was written.
9. **Given** any command's prep screen with some fields edited away from
   their opening values, **When** the user triggers Restore Defaults,
   **Then** every field resets to the value it had when the screen first
   opened (including a non-empty default, where one exists) — not
   necessarily blank — by reloading the prep screen itself rather than
   resetting each field individually.
10. **Given** a run currently in progress, **When** the user is on that
    command's prep screen (having navigated back mid-run, or before
    navigation completes), **Then** Restore Defaults has no effect until
    that run finishes, consistent with fields already being disabled for
    the duration of a run.

### Edge Cases

- What happens to a field label long enough to threaten the frame's width
  (e.g. `voxel_size_unit` → "Voxel Size Unit")? It must wrap to a second
  line without breaking the frame's border, never truncating text away.
- What happens on a command with zero optional fields, or zero required
  fields? Only the frame for the group that has fields is shown (User Story
  2, Acceptance Scenario 2) — no empty frame, and so no remaining-count
  subtitle either when there are no required fields to count.
- What happens to the required frame's subtitle when a required field
  starts pre-filled with a default value? It counts as filled from the
  first render — the subtitle reflects truly empty fields, not fields the
  user hasn't yet touched.
- What happens to the logo on a terminal resize while the menu is open? It
  re-evaluates the same width/height rule (User Story 1, Acceptance
  Scenario 2) — appears/disappears consistently with the current size.
- What happens to the enlarged command list on a short terminal where the
  taller rows no longer all fit? The list scrolls, consistent with how
  other content areas in the app already handle overflow, rather than
  shrinking rows back down or clipping entries.
- What happens when Browse is pressed on a field whose current value is any
  recognized remote path? Browse only picks local filesystem paths —
  typing remains the only way to enter a remote URL; the button is still
  shown, but its picker only ever lists local entries.
- What happens when the directory-tree view encounters a permission-denied
  entry? It must not crash — consistent with the existing path
  autocomplete's own tolerance for unreadable entries, that entry is
  skipped or shown as unexpandable.
- What happens if the user pastes a full remote URL in one action rather
  than typing it character by character? The same detection applies
  immediately in one step — it doesn't require incremental typing to
  trigger.
- What happens if the field's value is exactly one of the bare schemes
  (e.g. `gs://`) with nothing after it? No add-on is shown yet — it stays a
  single editable input containing that text, consistent with the
  reversibility behavior in User Story 5, Acceptance Scenario 3.
- What happens if the user returns to the prep screen while a run is
  still pending (via the Result screen's return shortcut) and presses Run
  again for that same command? The app does not start a second execution
  — it re-navigates to that same still-pending Result screen, unchanged,
  rather than cancelling the first run or opening a duplicate screen.
- What happens if the user presses Cancel/Escape instead of Run? No
  execution occurs, so there is nothing to navigate to — this exits the
  app the same way it already does, unchanged by User Story 7.
- What happens to the Command Identity Frame's name/description for a
  specialized screen with no directly corresponding `click.Command` help
  text at the point it's rendered? It uses that command's existing CLI
  help text exactly as the command menu already does (User Story 6,
  Acceptance Scenario 2) — never screen-specific wording.
- What happens if the command finishes so quickly that the progress
  indicator would barely be visible? The Result screen still opens
  immediately on Run and briefly shows the pending state — there is no
  minimum display duration, it swaps to the outcome as soon as the result
  arrives.
- What happens to Restore Defaults if the prep screen has no fields with
  non-default values (nothing to reset)? The screen still reloads, but
  since every field already shows its opening value, the visible result
  is unchanged.
- What happens to a specialized screen's other live content (e.g.
  `config`'s current-vs-defaults view) when Restore Defaults reloads the
  screen? It resets too, along with the fields — reloading rebuilds the
  whole screen from scratch, the same as opening it fresh from the menu,
  not just the input fields. (`fix_metadata`/`migrate`'s prep screens no
  longer carry live preview content of their own — see User Story 8 — so
  for them this now just resets the collected arguments.)

### User Story 8 - Confirm before you commit changes (Priority: P8)

A user fills in `fix_metadata`'s or `migrate`'s prep screen — just the
arguments those commands actually take (`ZARR_PATH`, and `migrate`'s
`--target_version`) — and presses Run. Instead of executing right away,
the app takes them to a dedicated Command Confirm screen for that
command, showing what would happen before anything is written. For
`migrate` (auto mode — its CLI needs no further interactive input beyond
its flags), the Confirm screen shows the `ZARR_PATH` in a disabled field,
then either a message that the dataset is already at the target version
(nothing to do) or a side-by-side diff of the current metadata beside
what migrating would produce. For `fix_metadata` (interactive mode — its
CLI has no flags at all beyond `ZARR_PATH`, prompting interactively for
everything else), the Confirm screen shows the same disabled path field,
then a Rich-styled window of editable fields mirroring the CLI's own
prompts (image name, spatial unit, voxel size, axis names) pre-filled
with the same defaults those prompts show, with a live side-by-side diff
below that updates as the fields are edited. On either screen, a
"Confirm" shortcut (in place of "Run") is what actually executes the
change and takes the user to that command's existing Result screen;
`fix_metadata`'s Confirm screen also gets a Restore Defaults shortcut
that resets its fields back to the computed defaults. An "escape" shortcut
returns to the prep screen beneath, with its field values unchanged.

**Why this priority**: The most recently requested change, and scoped
narrowly to the two commands that mutate a dataset's metadata in a way
worth reviewing first — every other command keeps its existing immediate-Run
behavior (User Story 7) unchanged.

**Independent Test**: Open `migrate`'s prep screen, fill in `ZARR_PATH`,
press Run, and confirm the app shows the Confirm screen (not the Result
screen) with the path disabled and either the "nothing to do" message or
a side-by-side diff, depending on whether the dataset is already at the
target version; press Confirm and confirm it then executes and shows the
Result screen. Separately, open `fix_metadata`'s prep screen, fill in
`ZARR_PATH`, press Run, and confirm its Confirm screen shows editable
prompt-style fields pre-filled with computed defaults and a live diff
that updates as they're edited; press Confirm and confirm it writes and
shows the Result screen.

**Acceptance Scenarios**:

1. **Given** `fix_metadata`'s or `migrate`'s prep screen with `ZARR_PATH`
   filled in, **When** the user presses Run, **Then** the app navigates
   to that command's Confirm screen rather than executing anything —
   nothing on disk changes yet.
2. **Given** the Confirm screen for either command, **When** it renders,
   **Then** `ZARR_PATH` is shown in a disabled (non-editable) field,
   carried over from the prep screen.
3. **Given** `migrate`'s Confirm screen where the dataset is already at
   the target version, **When** it renders, **Then** it shows a message
   that there is nothing to do, with no diff panels; pressing Confirm in
   this state does nothing (no execution, no navigation).
4. **Given** `migrate`'s Confirm screen where migration is needed,
   **When** it renders, **Then** it shows two side-by-side panels — the
   current metadata and what migrating would produce.
5. **Given** `fix_metadata`'s Confirm screen, **When** it renders,
   **Then** it shows editable fields for image name, spatial unit, voxel
   size, and axis names, each pre-filled with the same default the CLI's
   own interactive prompt for that value would show.
6. **Given** `fix_metadata`'s Confirm screen, **When** the user edits any
   of those fields, **Then** the side-by-side diff below updates to
   reflect the new proposed metadata.
7. **Given** `fix_metadata`'s Confirm screen with a field edited away
   from its default, **When** the user triggers Restore Defaults,
   **Then** every field resets to its originally computed default and
   the diff updates to match.
8. **Given** `fix_metadata`'s Confirm screen with an unparseable voxel
   size, **When** the user presses Confirm, **Then** nothing executes and
   an inline error is shown — the same "block, don't crash" precedent
   already established for invalid input elsewhere in this app.
9. **Given** either Confirm screen in a state where executing is valid,
   **When** the user presses Confirm, **Then** the change is applied and
   the app navigates to that command's existing Result screen, exactly as
   User Story 7 already describes for every other command's Run.
10. **Given** either Confirm screen, **When** the user presses its escape
    shortcut, **Then** the app returns to the prep screen beneath it with
    its field values unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The command menu screen MUST display a static logo above the
  command list: three filled, bottom-aligned squares of decreasing size
  (4×4, 3×3, 2×2), side by side, each in one of OME's three brand colors.
- **FR-002**: The logo MUST be hidden, not clipped or corrupted, when the
  terminal is too narrow or too short to fit it above the command list.
- **FR-002a**: The command menu MUST remain the `OptionList` widget, with
  each `Option`'s content built as a 3-line Rich renderable (up from today's
  1-line plain text): the command name, its existing one-line CLI help
  text, and a blank spacing line — without changing existing selection
  behavior (arrow-key/click highlight, Enter to open).
- **FR-002b**: The enlarged command list MUST remain scrollable rather than
  shrinking or clipping when it doesn't fully fit the terminal height.
- **FR-002c**: A command menu entry's help-text line MUST be sourced
  directly from that command's existing CLI help text, never a separately
  maintained copy, and MUST render blank (not an error) for a command with
  no help text.
- **FR-003**: Every command form (generic and specialized) MUST present
  required fields grouped together and positioned before optional fields.
- **FR-004**: Required fields MUST be enclosed in one titled, bordered
  frame; optional fields MUST be enclosed in a separate titled, bordered
  frame. A group with no fields MUST NOT render an empty frame.
- **FR-004a**: The required-fields frame MUST use a solid red border style;
  the optional-fields frame MUST use a solid blue border style.
- **FR-004b**: The required-fields frame's border subtitle MUST show the
  count of required fields that are currently empty (e.g. "2 remaining"),
  recomputed whenever a required field's value changes, including reaching
  "0 remaining" when all are filled.
- **FR-005**: Field labels MUST be rendered as capitalized, space-separated
  words derived from the parameter's name, instead of the raw CLI
  flag/argument name.
- **FR-006**: Individual field labels MUST NOT carry a per-field
  required marker — required-ness is conveyed solely by the "Required"
  field-group frame (FR-004a) a field is grouped under, avoiding a
  redundant marker alongside the new label casing and frame layout.
- **FR-006a**: A field label too long to fit the frame's width MUST wrap
  to a second line rather than truncating — no label text may be hidden
  from the user, and the frame's border MUST NOT break as a result.
- **FR-007**: Grouping fields into frames and relabeling them MUST NOT
  change the CLI tokens/invocation the form produces — Run, Copy, and Copy &
  exit MUST continue to use each field's original parameter name/flag,
  unaffected by its display label or which frame it's shown in.
- **FR-008**: Every path-typed field (`click.Path` parameters) MUST show a
  3-row "Browse" button to the right of its input.
- **FR-009**: Pressing Browse MUST open a `DirectoryTree`-based view of the
  local filesystem, rooted at the field's current value's parent directory
  if set, otherwise the current working directory.
- **FR-009a**: The directory-tree view MUST provide a way to navigate to
  a directory outside the current root's descendants — e.g. an ancestor
  or sibling of wherever the picker happened to open — since a directory
  tree by itself only exposes its root's descendants. This MUST NOT
  depend solely on a specific physical key (e.g. Backspace), since key
  delivery is not guaranteed to be identical across every
  terminal/multiplexer; an editable, pre-filled path field the user can
  type into and submit satisfies this without that dependency.
- **FR-010**: Selecting an entry in the directory-tree view MUST fill the
  corresponding field with that path and return to the form without
  altering any other field's value; dismissing without selecting MUST leave
  the field unchanged.
- **FR-011**: The directory-tree view MUST only allow selecting entries
  consistent with the field's declared constraint (directory-only,
  file-only, or either), matching what the field's `click.Path` type
  already accepts.
- **FR-012**: The directory-tree view MUST tolerate permission-denied
  entries without crashing, consistent with the existing path
  autocomplete's behavior (`SafePathAutoComplete`).
- **FR-013**: Browse MUST NOT replace typing — the existing Input +
  autocomplete behavior for path fields MUST remain available and
  unaffected.
- **FR-014**: A path field whose current value starts with any of the
  tool's recognized remote schemes (`gs://`, `gcs://`, `s3://`, `az://`,
  `abfs://`, `http://`, `https://`) followed by at least one more character
  MUST render that scheme as a distinct, non-editable, colored add-on
  positioned to the left of the input, with only the remaining text
  editable inside the input itself.
- **FR-015**: Add-on color MUST be assigned by provider: blue for
  `gs://`/`gcs://` (Google Cloud Storage), orange for `s3://` (AWS S3),
  cyan for `az://`/`abfs://` (Azure), and a neutral gray for the
  provider-agnostic `http://`/`https://`.
- **FR-016**: A path field in either add-on state MUST NOT offer
  local-filesystem autocomplete suggestions.
- **FR-017**: If the user deletes the input's editable text down to empty
  while an add-on is shown, the scheme prefix MUST be restored as ordinary
  editable text inside the input, and the add-on MUST be removed, so the
  user can continue deleting it if they choose.
- **FR-018**: The add-on treatment MUST NOT change the CLI token/value the
  field contributes — the full path (scheme + remainder) sent to Run,
  Copy, and Copy & exit MUST be identical to what a single plain-text field
  containing the same full value would produce.
- **FR-019**: A path field's Browse button (User Story 4), where present,
  MUST remain positioned to the right of the whole field (add-on + input)
  when shown, but MUST be hidden while the remote-path add-on (User
  Story 5) is shown, since browsing the local filesystem does not apply
  to a remote path; it reappears once the add-on is removed.
- **FR-020**: Every command prep screen MUST display a block above its
  field content showing the command's name in bold, with its existing
  CLI description text underneath, sourced identically to the command
  menu's entry (FR-002c) — never a separately maintained copy.
- **FR-021**: The command-identity block (FR-020) MUST be visually
  distinguishable from the required/optional field-group frames (FR-004a)
  — it is borderless (unlike the field-group frames' solid borders) and
  its description is capped at 3 lines regardless of length, so a screen
  showing both cannot visually conflate them or let a long description
  push the rest of the screen down.
- **FR-022**: Pressing Run, once all required fields are filled, MUST
  immediately navigate to a dedicated Command Result screen for that
  command — the app MUST NOT wait for the command to finish before
  navigating.
- **FR-022a**: The Command Result screen MUST display the same
  command-identity frame (FR-020) as the prep screen it was opened from,
  sourced the same way, for as long as the screen is shown.
- **FR-022b**: While the command is still executing, the Command Result
  screen MUST show a progress bar (once progress is quantifiable) or an
  animated sparkline (while it isn't yet) in place of the outcome
  content, using the same status-indicator behavior already established
  for command screens.
- **FR-022c**: Once the command finishes, whether it succeeds or fails,
  the Command Result screen MUST replace the progress indicator with the
  outcome — a success/failure indicator plus the content described in
  FR-023/FR-024 — without requiring the user to take any action.
- **FR-023**: Every Command Result screen MUST share one common base
  implementation providing: the command-identity frame (FR-022a), the
  pending-state progress indicator (FR-022b), a success/failure
  indicator once finished, the execution log, and a shortcut back to that
  command's prep screen with its field values preserved, available in
  both the pending and finished state.
- **FR-024**: Each command's Command Result screen MUST additionally
  present, once finished, that command's own specific output: `inspect`'s
  summary/JSON report, `fix_metadata`'s/`migrate`'s applied diff,
  `config`'s resulting JSON, and the captured execution log for every
  other command.
- **FR-025**: Pressing Run while a required field is empty MUST NOT
  trigger navigation to the Result screen — the existing inline
  validation notification applies unchanged, since the command never
  executes.
- **FR-025a**: Pressing Run for a command whose Result screen is already
  showing a pending (not-yet-finished) run MUST NOT start a second
  execution — it MUST re-navigate to that same pending Result screen.
- **FR-026**: Returning from the Result screen to the prep screen MUST NOT
  alter any field's value from what it was immediately before Run, in
  either the pending or finished state.
- **FR-027**: Every command prep screen MUST provide a Restore Defaults
  action that resets every field to the value it held when the screen was
  first opened (its original default, or blank where there is none) — not
  necessarily to an empty state — by reloading the prep screen rather than
  resetting individual field values.
- **FR-027a**: Restore Defaults MUST have no effect while the screen's
  fields are disabled for the duration of a run.
- **FR-028**: `fix_metadata`'s and `migrate`'s prep screens MUST collect
  only the arguments those commands actually take (`ZARR_PATH`, and
  `migrate`'s `--target_version`) — no live preview content of any kind —
  and MUST NOT execute anything when Run is pressed; every other
  command's prep screen is unaffected and keeps User Story 7's
  immediate-Run behavior unchanged.
- **FR-029**: Pressing Run on `fix_metadata`'s or `migrate`'s prep screen
  (once its required fields are filled) MUST navigate to a Command
  Confirm screen for that command, sharing the same identity-frame +
  bottom-bar template as the prep and Result screens, instead of
  executing directly.
- **FR-030**: Every Command Confirm screen MUST show the collected
  `ZARR_PATH` in a disabled (non-editable) field.
- **FR-031**: `migrate`'s Confirm screen ("auto" mode — its CLI needs no
  further interactive input beyond its flags) MUST show either: (a) a
  message that the dataset is already at the target version, when true,
  with no diff shown, or (b) two side-by-side panels — current metadata
  and what migrating would produce — when a migration is actually needed.
- **FR-032**: `fix_metadata`'s Confirm screen ("interactive" mode — its
  CLI has no flags beyond `ZARR_PATH`, prompting for everything else)
  MUST show editable fields for image name, spatial unit, voxel size, and
  axis names, each pre-filled with the same default value the CLI's own
  `click.prompt()` calls would show, computed by the same shared function
  the CLI uses. Editing any of these fields MUST update a live
  side-by-side diff (current metadata vs. the proposed result) shown
  below them.
- **FR-032a**: `fix_metadata`'s Confirm screen MUST provide a Restore
  Defaults action that resets its four fields to their originally
  computed defaults (and refreshes the diff to match), independent of
  the prep screen's own Restore Defaults (FR-027).
- **FR-033**: Every Command Confirm screen MUST provide a "Confirm"
  shortcut (in place of "Run") that executes the change — writing
  metadata or applying the migration — and, on success or failure,
  navigates to that command's existing Result screen (User Story 7),
  exactly as pressing Run already does for every other command.
  `fix_metadata`'s Confirm action MUST validate its fields first (e.g.
  voxel size must parse as three numbers) and MUST NOT execute or
  navigate anywhere if validation fails, showing an inline error instead.
  `migrate`'s Confirm action MUST be a no-op (no execution, no
  navigation) while its screen is in the "already at target version"
  state.
- **FR-034**: A Command Confirm screen MUST provide a way back to the
  prep screen beneath it (its escape shortcut) that leaves every field's
  value exactly as it was, matching the existing Back-to-form precedent
  (FR-026).
- **FR-035**: The side-by-side diff (FR-031/FR-032) MUST also replace the
  single unified diff view `fix_metadata`'s and `migrate`'s Result
  screens previously used, so both screens present diffs the same way.

### Key Entities

- **Logo**: Three filled, bottom-aligned squares (sides 4/3/2) side by
  side, one per OME brand color (red/green/blue), shown above the command
  menu's list, hidden below a minimum terminal size.
- **Command Menu Entry**: A single, selectable, 3-line highlightable block
  in the command menu's list (up from today's 1-line list item): command
  name, its existing CLI help text, and a blank spacing line.
- **Field Group Frame**: A titled, bordered container (1-character margin
  and padding, sized to its content rather than expanding to fill the
  screen) holding either all of a form's required fields or all of its
  optional fields; omitted entirely if that group is empty. The required
  frame uses a solid red border and a subtitle showing its still-empty
  field count; the optional frame uses a solid blue border.
- **Field Label**: The human-readable, capitalized/space-separated text
  shown next to a field, derived from (but never altering) the underlying
  CLI parameter name.
- **Browse Picker**: A 3-row button beside a path field's input (hidden
  while that field's remote-path add-on is shown); opens a
  `DirectoryTree`-based view rooted near the field's current value, with
  an editable, pre-filled path field above the tree the user can submit
  to re-root anywhere (since the tree otherwise can't reach directories
  outside the current root's descendants), constrained to
  directories/files per the field's type, that fills the field on
  selection and leaves it unchanged on cancel.
- **Remote Path Add-on**: A non-editable, provider-colored prefix (blue:
  `gs://`/`gcs://`; orange: `s3://`; cyan: `az://`/`abfs://`; gray:
  `http://`/`https://`) shown to the left of a path field's input when its
  value starts with that scheme and has additional text after it; reverts
  to plain editable text (scheme included) when the remainder is emptied.
- **Command Identity Frame**: A borderless block showing the command's
  name in bold with its existing CLI description text underneath (capped
  at 3 lines); shown at the top of every prep screen above the field
  content, and reused unchanged at the top of that command's Result
  screen; visually distinct from the required/optional field-group
  frames' solid borders.
- **Command Result Screen**: The screen the app navigates to immediately
  on Run (not after it finishes). One shared base class provides common
  chrome (the Command Identity Frame, a pending-state progress
  bar/sparkline, a success/failure indicator once finished, the execution
  log, and a return shortcut back to the prep screen, preserved fields
  intact); each command's own subclass adds its finished-state specific
  output (report panels, diff, config JSON, or captured log).
- **Restore Defaults**: A prep-screen action resetting every field to the
  value it held when the screen first opened (its original default, or
  blank), achieved by reloading the whole prep screen rather than
  resetting individual field values; has no effect while fields are
  disabled during a run.
- **Command Confirm Screen**: `fix_metadata`'s and `migrate`'s screen
  between the prep and Result screens, sharing the same identity-frame +
  bottom-bar template. Shows the collected `ZARR_PATH` in a disabled
  field, then either "auto" mode content (`migrate`: an
  "already at target version" message, or the side-by-side diff) or
  "interactive" mode content (`fix_metadata`: a Rich-styled window of
  fields mirroring the CLI's own prompts, pre-filled with the same
  defaults, plus a live side-by-side diff). A "Confirm" shortcut (in
  place of "Run") executes and navigates to the Result screen;
  `fix_metadata`'s screen also gets its own Restore Defaults, independent
  of the prep screen's.
- **Side-by-Side Diff**: Two bordered, titled panels ("Current" /
  "Proposed") shown next to each other, each pretty-printed JSON with
  replaced/removed lines highlighted red on the left and
  replaced/added lines highlighted green on the right; used by the
  Command Confirm screen (auto mode and interactive mode alike) and by
  `fix_metadata`'s/`migrate`'s Result screens, replacing the single
  unified diff view those Result screens previously used.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The command menu shows the ASCII logo at standard terminal
  sizes (80×24 and larger), verified by screen inspection.
- **SC-001a**: Every command menu entry renders as exactly a 3-line
  highlightable block (up from today's 1 line), with selection/open
  behavior unchanged.
- **SC-002**: 100% of command forms with a mix of required/optional fields
  show two frames (Required, Optional), with all required fields inside the
  first and all optional fields inside the second, the first in a solid red
  border and the second in a solid blue border.
- **SC-002a**: On every command form with at least one required field, the
  required frame's subtitle always matches the true count of currently
  empty required fields, verified after every field edit.
- **SC-003**: 100% of field labels across every command form display as
  human-readable text with no raw CLI flag characters (`--`, leading `-`,
  underscores) visible.
- **SC-004**: For every command form, the CLI invocation produced after
  this redesign is byte-for-byte identical (for the same field values) to
  what it was before — verified by comparing generated tokens, not just
  visual output.
- **SC-005**: 100% of path-typed fields across every command form show a
  Browse button, and selecting an entry via the resulting picker produces
  the exact same field value (and thus CLI token) as typing that path
  directly would.
- **SC-006**: Every path field correctly shows the provider-colored add-on
  (blue/orange/cyan/gray per FR-015) the moment its value starts with a
  recognized remote scheme plus more text, with autocomplete suppressed in
  that state.
- **SC-007**: Deleting a field's remainder text back to empty always
  restores the scheme as plain editable text, verified across every path
  field in the app.
- **SC-008**: The CLI token produced by a path field is unaffected by
  add-on rendering — byte-for-byte identical to the same value typed as
  plain text, for every value tested.
- **SC-009**: 100% of command prep screens show a command-identity frame
  with the correct command name and description, verified by screen
  inspection.
- **SC-010**: 100% of command runs, whether they succeed or fail, navigate
  to that command's Result screen immediately on Run (or, for
  `fix_metadata`/`migrate` specifically, to their Confirm screen —
  User Story 8 — with the Result screen reached one step later via
  Confirm), and end there showing the correct success/failure indicator
  once finished.
- **SC-011**: Every command's Result screen shows that command's specific
  output (report/diff/config JSON/log) with no cross-command mixing,
  verified per command.
- **SC-012**: Returning from the Result screen to the prep screen never
  changes a field's value, verified across all command forms, from both
  the pending and finished state.
- **SC-013**: 100% of Result screens show a progress bar or animated
  sparkline while their command is still executing, verified by screen
  inspection during a run.
- **SC-014**: 100% of Result screens show the same command-identity frame
  content as their originating prep screen.
- **SC-015**: 100% of command prep screens' Restore Defaults action resets
  every field to its opening value, verified across all command forms.
- **SC-016**: 100% of the time, pressing Run on `fix_metadata`'s or
  `migrate`'s prep screen navigates to that command's Confirm screen
  without executing anything — verified by confirming the dataset is
  byte-for-byte unchanged until Confirm is actually pressed.
- **SC-017**: `migrate`'s Confirm screen correctly distinguishes the
  "already at target version" case (message, no diff, Confirm is a
  no-op) from the "migration needed" case (side-by-side diff shown,
  Confirm executes), verified against real datasets in both states.
- **SC-018**: `fix_metadata`'s Confirm screen's four prompt fields always
  start pre-filled with the same default values the CLI's own
  interactive prompts would show for the same dataset, verified by
  comparing against `compute_default_prompt_values()`'s output directly.

## Assumptions

- **Required-before-optional ordering**: the user asked to "reorder the
  fields whether they are required or optional" without specifying which
  group comes first; required-first is assumed as the standard convention
  (users must address these to submit; optional fields are secondary), and
  frames are only visually reordered — no field's underlying parameter
  changes.
- **Logo placement**: shown on the command menu (the app's "home" screen)
  only, not repeated on every per-command form screen, to avoid eating
  vertical space on forms with many fields — `003` already established the
  header/status-log/footer skeleton those screens rely on.
- **"Larger" menu items**: the menu stays an `OptionList` (per the user's
  explicit direction), but each `Option`'s content becomes a 3-line Rich
  renderable instead of plain text: line 1 is the command name, line 2 is
  that command's existing one-line CLI help text (same never-duplicated
  sourcing principle as User Story 3's labels), line 3 is blank spacing for
  visual weight. This also means a command with no help text shows a blank
  second line rather than an error.
- **Toad's logo**: the user's direct request, not something independently
  verified in Toad's own published screenshots/docs during research for
  this spec — implemented because it was explicitly asked for, not because
  Toad was confirmed to have one.
- **OME's three brand colors**: `#df283f` (red), `#16a34a` (green),
  `#1d8dcd` (blue) — sourced from openmicroscopy.org's own stylesheet, with
  the green adjusted from an initially-scraped `#128669` because that value
  and the blue collapse to the same ANSI color on terminals without
  truecolor support, making them indistinguishable; `#16a34a` downgrades to
  actual ANSI green instead. Logo squares are rendered at `side × 2`
  character-columns wide (vs. `side` rows tall) to compensate for terminal
  character cells being roughly twice as tall as wide — otherwise an N×N
  character block reads as a vertical rectangle, not a square.
- **Dolphie/Harlequin as inspiration, not literal ports**: neither app's
  domain matches this tool's (Dolphie: live DB metrics dashboards; Harlequin:
  three-pane DB client). What transfers is the shared *aesthetic
  principle* — clean, titled, bordered panels organizing information without
  clutter — applied here to User Story 2's field-group frames, not their
  specific real-time-graph or three-column layouts.
- Label casing (User Story 3) is a *display-only* transformation; it does
  not rename any `click.Parameter`, flag, or config key anywhere in the
  codebase.
- **Widget variety**: the user's opening framing ("use other widgets that
  are available instead of input fields all the time") is treated as the
  rationale for User Story 4's Browse/`DirectoryTree` picker specifically,
  not a request to also change how boolean (`Checkbox`) or choice (`Select`)
  fields already work — those already use non-`Input` widgets today per
  `tui/fields.py`; only path fields still rely on `Input` alone.
- **Reintroducing a `Button`**: `002` deliberately removed all buttons from
  the TUI in favor of footer keyboard shortcuts, and a later paste-button
  experiment was reverted for the same reason. User Story 4's Browse button
  is a scoped, explicit exception the user asked for directly — it opens a
  picker, it doesn't run a command or duplicate a footer shortcut, so it
  doesn't reintroduce the confirmation-dialog/redundant-click pattern `002`
  was avoiding.
- **Add-on scheme scope**: extended to every remote scheme the tool's
  `core/zarr_path.py` already recognizes (`gs://`, `gcs://`, `s3://`,
  `az://`, `abfs://`, `http://`, `https://`), not just `gs://`/`s3://` —
  per the user's explicit "handle other remote schemes in the same way."
- **Add-on colors**: `gs://`/`s3://` use blue/orange respectively (the
  user's corrected mapping, matching each provider's more common brand
  association: AWS orange, Google Cloud blue). `gcs://` is treated as an
  alias for `gs://` and shares its color. `az://`/`abfs://` (Azure) are
  assigned cyan — a color distinct from both blue and orange, since Azure
  wasn't named by the user and needed its own unambiguous choice.
  `http://`/`https://` carry no cloud-provider identity, so they get a
  neutral gray rather than a borrowed brand color. Exact shade for each is
  a `/speckit-plan` detail, chosen from Textual's built-in color palette.
- **Autocomplete today has no dynamic disable**: `build_autocomplete` in
  `tui/fields.py` currently attaches `SafePathAutoComplete` once at form
  build time, rooted from whatever the field's initial value is, with no
  existing mechanism to turn it on/off as the value changes later. FR-016
  is new dynamic behavior, not a tweak to something that already reacts to
  keystrokes.
- **Command Identity Frame styling**: borderless (bold name + description
  underneath, capped at 3 lines, a bit of padding) so it reads distinctly
  from the solid red/solid blue field-group frames (User Story 2) at a
  glance, per explicit user direction.
- **"Command result page" scope**: applied uniformly to every command,
  including `inspect`/`fix_metadata`/`migrate`/`config`, which already
  show rich preview content (report/diff/current-config) inline, live,
  *before* Run is pressed. User Story 7 does not remove those existing
  pre-run previews — it adds a post-run destination that shows the
  actual, applied result (not just the preview) once execution finishes.
- **Result screen navigation model**: implemented as `push_screen`, so
  Back (`pop_screen`) returns to the exact prep-screen instance with its
  field values intact — the same screen-stack pattern already used for
  Menu → Prep navigation, rather than rebuilding the prep screen from
  scratch or returning to the menu.
- **Generic commands' result content**: `from_images`/`extract`/
  `apply_mask` (and any future command without a specialized screen) show
  their captured execution output/log as their command-specific Result
  content, since they don't produce a report/diff/config object today.
- **Progress indicator reuse**: FR-022b's progress bar/animated sparkline
  is the same status-indicator behavior this app already has (spec 002 US5
  — a progress bar once progress is quantifiable, an animated sparkline
  before then), relocated onto the Result screen rather than reinvented;
  the prep screen's own copy of that indicator is simply not driven for a
  Run any more, since the user has already navigated away from it by the
  time it would show anything.
- **Return-shortcut label**: the user asked for a better name than
  "return to command prep" for the Result screen's return-to-prep
  shortcut. Named **"Back to form"** — short enough for the footer,
  unambiguous about the destination (unlike the generic "Back to menu"
  label every other screen's escape binding uses, which would be
  literally inaccurate here since one press returns to the prep screen,
  not the menu). This is a deliberate, scoped exception to
  `shared_bindings()`'s existing "only the primary action's label may
  vary" rule (`003`'s own contract) — the Result screen is the one screen
  where the generic label would actively mislead.
- **Restore Defaults' key binding**: `F4`, chosen because it's unused
  today and sits immediately before Run (`F5`) in the footer's
  left-to-right order, reading naturally as "Restore Defaults, then Run."
  Unchanged from this feature's earlier "Clear" naming — only the label
  and the reset mechanism changed, not the key.
- **Restore Defaults resets to opening values, not blank**: some fields
  have a meaningful non-empty default (e.g. `migrate`'s
  `--target_version`); resetting those to empty would be less useful than
  restoring what the screen showed on first open.
- **Restore Defaults reloads the screen rather than resetting fields
  individually**: per the user's explicit direction, implemented by
  replacing the current prep screen with a freshly constructed instance
  of the same screen class (Textual's `App.switch_screen()`, confirmed to
  replace only the top of the screen stack without growing it) rather
  than recording each field's opening value and writing it back — this
  supersedes this feature's earlier per-field "record and restore"
  design. A fresh instance recomputes every default through the exact
  same code path used when the screen was first opened, so there is only
  ever one source of truth for "what a field's default is," and it
  naturally also resets non-field content (previews, diffs) for the
  specialized screens as a side effect, not just input fields.
- **Re-pressing Run against a pending Result screen**: rather than
  starting a second execution (`execution.py`'s worker is already
  `exclusive=True`, so a second call would silently cancel the first) or
  doing nothing, the prep screen holds a reference to its in-flight
  Result screen and re-navigates to it — the simplest option that can't
  orphan a cancelled run's Result screen waiting forever for a result
  that will never arrive.
- **"Auto" vs. "interactive" Confirm mode is fixed per-command, not a
  runtime toggle**: `migrate`'s CLI is entirely flag-driven (one
  `--target_version` option, no `click.prompt()` calls) so its Confirm
  screen never needs further input beyond what the prep screen already
  collected — "auto". `fix_metadata`'s CLI has no flags beyond
  `ZARR_PATH` at all, prompting interactively for everything else — its
  Confirm screen always needs the Rich prompt window — "interactive".
  Since which mode applies is entirely determined by each command's own
  existing CLI shape, there's no scenario where the same command would
  need both, so no mode-selection UI exists.
- **Confirm executes directly, with no separate subsequent Run press**:
  per explicit user direction — Form's Run navigates to Confirm; Confirm
  (not a further Run) is the single action that both locks in the
  reviewed values and executes them. This differs from an earlier phrase
  in this session ("fix_metadata should also wait for Run") which turned
  out to describe Form waiting for its own Run press before navigating
  to Confirm, not a second Run step after Confirm.
- **Scope limited to `fix_metadata`/`migrate`**: per the user's explicit
  instruction to ask before extending this to other commands, no other
  command's prep screen was changed — every other command keeps User
  Story 7's immediate-Run behavior unchanged.
- **`ZARR_PATH` Browse-picker directory-selection bug, found and fixed
  alongside this feature**: `extract`/`fix_metadata`/`migrate`/`inspect`'s
  `zarr_path` argument was declared as `ZarrPathParamType(exists=True)`
  with no `file_okay=False`, unlike `apply_mask`'s already-correct
  `volume`/`mask` fields — so their Browse picker's `only` constraint
  resolved to `"any"` instead of `"dir"`, and `BrowsePickerScreen` only
  dismisses on `DirectorySelected` when `only == "dir"` (FR-011). A Zarr
  store is always a directory, never a plain file, so selecting a folder
  in these four commands' pickers only expanded/collapsed it in the tree
  instead of choosing it — fixed by adding `file_okay=False` to all four,
  matching `apply_mask`'s existing pattern. Pre-existing bug, unrelated
  to User Story 8's new screens, surfaced by the user while testing them.
