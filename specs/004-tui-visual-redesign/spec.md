# Feature Specification: TUI Visual Redesign

**Feature Branch**: `004-tui-visual-redesign`

**Created**: 2026-08-06

**Status**: Draft

**Input**: User description: "the TUI is ugly, I want to pimp it a bit. Like in Toad, add a logo at the top; that logo can be Matriochka doll inspired in ASCII. In forms, reorder the fields whether they are required or optional, add frame boxes and edit case (the current case matches the CLI conventions, but that is not pretty). Also look at the Dolphie and Harlequin examples: https://textual.textualize.io/"

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
out of scope for those two changes. The header clock is the one exception:
since every screen already shares the same `Header` chrome (per `003`), it
appears everywhere, not just on the menu.

**Why this priority**: The single most requested, highest-visibility change
("add a logo at the top... like in Toad") — it's the first thing every user
sees, every time.

**Independent Test**: Open the command menu at a standard terminal size
(80×24 or larger) and confirm the ASCII logo renders above the command list,
that each command occupies a 3-line highlightable block rather than today's
1-line highlightable text, and that the header bar shows a live clock; open
any other screen and confirm the clock is still shown there too.

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
4. **Given** any screen in the app (not just the command menu — every
   screen already shares the same header chrome per `003`), **When** it is
   shown, **Then** the shared header bar displays a live clock, updating at
   least once per minute.

---

### User Story 2 - Forms that look designed, not dumped (Priority: P2)

A user opens any command's form (`from_images`, `extract`, `apply_mask`, or
the specialized `fix_metadata`/`migrate`/`inspect`/`config` screens) and
sees required fields grouped together, ahead of optional fields, each group
inside its own titled, bordered frame — instead of today's single
undifferentiated, unframed list in whatever order Click happened to declare
the parameters.

**Why this priority**: The second most concrete ask, and the highest-traffic
screens in the app (every command's data-entry surface); framed,
grouped forms are the core of "reorder the fields... add frame boxes."
Informed by Harlequin and Dolphie's shared use of clean, titled, bordered
panels to organize dense information without clutter.

**Independent Test**: Open a form with a mix of required and optional
fields (e.g. `from_images`); confirm all required fields appear inside one
titled frame, ahead of all optional fields in a second titled frame.

**Acceptance Scenarios**:

1. **Given** a command form with both required and optional fields,
   **When** it renders, **Then** required fields appear together in one
   bordered, titled frame, positioned before a second bordered, titled
   frame containing the optional fields.
2. **Given** a command form with only required fields (or only optional
   fields), **When** it renders, **Then** only the one relevant frame is
   shown — no empty frame for the other group.
3. **Given** the user submits the form (Run/Copy/Copy & exit), **When** the
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
   form, **When** the user views it, **Then** the required-field marker
   (currently a trailing `*`) is still present and legible.
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

### Edge Cases

- What happens to a field label long enough to threaten the frame's width
  (e.g. `voxel_size_unit` → "Voxel Size Unit")? It must wrap or truncate
  without breaking the frame's border.
- What happens on a command with zero optional fields, or zero required
  fields? Only the frame for the group that has fields is shown (User Story
  2, Acceptance Scenario 2) — no empty frame.
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
- **FR-002d**: The shared header bar MUST display a live clock, updating at
  least once per minute, on every screen in the app (not just the command
  menu), since every screen already shares the same header chrome.
- **FR-003**: Every command form (generic and specialized) MUST present
  required fields grouped together and positioned before optional fields.
- **FR-004**: Required fields MUST be enclosed in one titled, bordered
  frame; optional fields MUST be enclosed in a separate titled, bordered
  frame. A group with no fields MUST NOT render an empty frame.
- **FR-005**: Field labels MUST be rendered as capitalized, space-separated
  words derived from the parameter's name, instead of the raw CLI
  flag/argument name.
- **FR-006**: The required-field marker MUST remain visible and legible
  alongside the new label casing and frame layout.
- **FR-007**: Grouping fields into frames and relabeling them MUST NOT
  change the CLI tokens/invocation the form produces — Run, Copy, and Copy &
  exit MUST continue to use each field's original parameter name/flag,
  unaffected by its display label or which frame it's shown in.
- **FR-008**: Every path-typed field (`click.Path` parameters) MUST show a
  3-row "Browse" button to the right of its input.
- **FR-009**: Pressing Browse MUST open a `DirectoryTree`-based view of the
  local filesystem, rooted at the field's current value's parent directory
  if set, otherwise the current working directory.
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
  MUST remain positioned to the right of the whole field (add-on + input),
  unaffected by whether the add-on is shown.

### Key Entities

- **Logo**: Three filled, bottom-aligned squares (sides 4/3/2) side by
  side, one per OME brand color (red/green/blue), shown above the command
  menu's list, hidden below a minimum terminal size.
- **Command Menu Entry**: A single, selectable, 3-line highlightable block
  in the command menu's list (up from today's 1-line list item): command
  name, its existing CLI help text, and a blank spacing line.
- **Field Group Frame**: A titled, bordered container holding either all of
  a form's required fields or all of its optional fields; omitted entirely
  if that group is empty.
- **Field Label**: The human-readable, capitalized/space-separated text
  shown next to a field, derived from (but never altering) the underlying
  CLI parameter name.
- **Browse Picker**: A 3-row button beside a path field's input; opens a
  `DirectoryTree`-based view rooted near the field's current value,
  constrained to directories/files per the field's type, that fills the
  field on selection and leaves it unchanged on cancel.
- **Remote Path Add-on**: A non-editable, provider-colored prefix (blue:
  `gs://`/`gcs://`; orange: `s3://`; cyan: `az://`/`abfs://`; gray:
  `http://`/`https://`) shown to the left of a path field's input when its
  value starts with that scheme and has additional text after it; reverts
  to plain editable text (scheme included) when the remainder is emptied.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The command menu shows the ASCII logo at standard terminal
  sizes (80×24 and larger), verified by screen inspection.
- **SC-001a**: Every command menu entry renders as exactly a 3-line
  highlightable block (up from today's 1 line), with selection/open
  behavior unchanged.
- **SC-001b**: The header's clock is visible and updates at least once per
  minute on 100% of screens in the app.
- **SC-002**: 100% of command forms with a mix of required/optional fields
  show two frames (Required, Optional), with all required fields inside the
  first and all optional fields inside the second.
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
