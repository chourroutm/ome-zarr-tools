---

description: "Task list for TUI Visual Redesign"
---

# Tasks: TUI Visual Redesign

**Input**: Design documents from `/specs/004-tui-visual-redesign/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/visual-design-contract.md, quickstart.md

**Tests**: Included and REQUIRED — this project's constitution, Principle II
("Test-First Development"), is non-negotiable. Every implementation task
below is preceded by a failing-test task for the same behavior.

**Organization**: Tasks are grouped by user story (P1-P7, per spec.md),
in priority order. User Story 1 is already implemented and committed
(`3383bb8`) and is included here only for a complete record — its tasks
are pre-checked.

**Status**: User Stories 2-7 (T004-T052) implemented via `/speckit-implement`
— all new/changed behavior covered by tests, full suite (144 tests at the
time) green, `ruff`/`mypy` clean. T053 (a real-terminal manual pass, beyond
the extensive headless/`Pilot`-driven verification already exercised by the
test suite and during implementation) is the one item still open. User Story
8 (below) was added afterward, directly; full suite is now 168 tests, still
green.

**Post-implementation tweaks** (direct, outside `/speckit-implement`, still
covered by tests/quality gates): field-group frame borders changed from
"tall" to "solid" red/blue; both field-group frames given a 1-character
margin/padding and `height: auto;` so they size to content instead of
expanding; the Command Identity frame (T036) redesigned from a titled
gold-round-bordered frame to a borderless block (bold name, description
underneath capped at 3 lines, `padding: 1 2;`); a blank line
(`margin-bottom: 1;`) added between fields within each group (not after
the last); the remote-path add-on restyled to match `Input`'s own box
exactly (`border: tall $border-blurred;`, `padding: 0 2;`, `background:
$surface;`) instead of a plain colored label, fixing both its vertical
alignment with the `Input`'s text and its visual "thinness" mismatch;
per-field required-star markers removed (redundant with the "Required"
frame); Browse button hidden while a field's remote-path add-on is shown
(FR-019, reversed from its original "always visible" wording);
`BrowsePickerScreen` gained a way to reach directories outside its
initial root's descendants, since `DirectoryTree` can't do that on its
own (FR-009a) — this also surfaced and fixed 3 existing
`test_tui_browse_picker.py` tests whose `pilot.click(button)` calls had
started landing outside the default 80x24 test viewport as the
cumulative frame/margin/padding changes above pushed content further
down; each now calls `button.scroll_visible()` before clicking. This
went through two iterations: first a `backspace`-only "Up" key binding
(the user reported it didn't fire in their real terminal — physical
Backspace sends different byte sequences across terminals/multiplexers),
then a clickable `#up-button` + `#current-path` label (the user reported
this "does not work" too, without further detail), finally replaced
with an editable, pre-filled `#root-path-input` above the tree that
re-roots on submit (Enter) if the typed value is a valid directory —
avoiding any dependency on a specific key or click target entirely, and
letting the user jump straight to any path rather than one level at a
time.

**User Story 8 — Command Confirm screen** (added directly, outside a
formal `/speckit-specify`/`/speckit-implement` cycle, per the user's
detailed request + follow-up clarification; spec.md/data-model.md/the
contract updated to match): `fix_metadata`'s and `migrate`'s prep
screens now only collect arguments (`ZARR_PATH`, `+ --target_version`)
and wait for Run — no more live diff/rich-view preview there (FR-028).
Run navigates to a new Command Confirm screen (`F5` relabeled
"Confirm") instead of executing directly (FR-029): `migrate` ("auto"
mode, since its CLI is flag-driven) shows a disabled path field plus
either "already at target version" or the side-by-side diff (FR-031);
`fix_metadata` ("interactive" mode, since its CLI has no flags beyond
`ZARR_PATH` and prompts for everything else) shows the same disabled
path field plus a Rich-styled window of editable fields mirroring those
prompts, pre-filled via a new shared `compute_default_prompt_values()`
(FR-032), with a live side-by-side diff and its own Restore Defaults
(FR-032a). Confirm executes and pushes the existing Result screen
(FR-033), which — along with the Confirm screen itself — now shows
diffs as two side-by-side panels (`tui/diff.py`'s new
`build_side_by_side_diff()`, FR-035) instead of the old unified
`diff_lines`/`render_diff` log (removed). No other command's screen was
touched, per explicit instruction. Extracted `fix_metadata.py`'s
prompt-default logic into `compute_default_prompt_values()`/
`PromptDefaults` and made `parse_tuple_input` public, reused by both the
CLI and the new Confirm screen. Also fixed a pre-existing bug surfaced
while testing this: `extract`/`fix_metadata`/`migrate`/`inspect`'s
`zarr_path` argument was missing `file_okay=False` (unlike
`apply_mask`'s already-correct fields), so their Browse picker's
directory-selection never dismissed the picker — fixed by adding
`file_okay=False` to all four, matching `apply_mask`'s pattern.
Follow-up styling refinements per the user: field-to-field spacing
extracted into a shared `.field-gap` CSS class (`fields.py`'s
`FIELD_GAP_CSS`) so the Prompts window's fields visually match the
Required frame's exactly, not a separately duplicated margin; the
Prompts window mirrors the Required frame's border style/spacing but in
green rather than red; the side-by-side diff gained matching left/right
margins and line-padding so replaced blocks of differing length don't
leave the two panels' later lines on different rows; and a real bug was
found and fixed where `Vertical`/`Horizontal`'s default `height: 1fr;
overflow: hidden hidden;` silently clipped a diff taller than its
container (`#confirm-diff`, `#result-content`, and the diff's own
`Horizontal` all needed explicit `height: auto;`) — overflow is now
handled entirely by each screen's own outer `VerticalScroll`, not a
nested, independently-scrollable region (an intermediate design that
also cropped content instead of making it reachable).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files/regions, no dependency on an unfinished task)
- **[Story]**: Which user story this task belongs to
- File paths are exact, relative to the repository root

## Phase 1: Setup

No setup tasks. Dependencies, environment, and lint/type/test tooling are
unchanged from features `001`-`003` (plan.md's Technical Context) — nothing
to initialize before Phase 3.

## Phase 2: Foundational (Blocking Prerequisites)

No tasks block *every* remaining user story simultaneously — unlike
`FieldSpec`/`build_field_frames()`, which is a real prerequisite but only
for User Stories 2-5 specifically (captured under that story's own phase
and in "User Story Dependencies" below), User Stories 6 and 7 have no
shared blocking prerequisite beyond code already shipped in User Story 1.
Proceed directly to Phase 3.

---

## Phase 3: User Story 1 - A distinctive first impression (Priority: P1) 🎯 MVP — ALREADY SHIPPED

**Goal**: A static OME-colored-squares logo above the command menu, plus
3-line Rich `OptionList` entries.

**Status**: Implemented and committed in `3383bb8` ("Add command menu logo,
3-line Rich menu entries, and a header clock" — the header-clock part was
later reverted in `9ed82e5`/`ec3b165`; the logo/menu-entry part described
here still stands). Listed for a complete task record only.

- [X] T001 [US1] Add `LOGO_BOXES`, `render_logo()`, `Logo(Static)` (with `set_visible_for_size()`) in `src/ome_zarr_tools/tui/logo.py`
- [X] T002 [US1] Add `_menu_option_prompt()` and wire `Logo` + 3-line `OptionList` entries into `CommandMenuScreen` in `src/ome_zarr_tools/tui/app.py`
- [X] T003 [US1] Add regression tests in `tests/integration/test_tui_logo.py` and `tests/integration/test_tui_menu.py`

**Checkpoint**: User Story 1 fully functional — verified via headless screenshot inspection at commit time.

---

## Phase 4: User Story 2 - Forms that look designed, not dumped (Priority: P2)

**Goal**: Required/optional field-group frames (solid red / solid blue,
live still-empty-count subtitle on the required frame) on every prep
screen.

**Independent Test**: Open `from_images`; confirm a tall-red "Required"
frame (with a correct, live-updating "N remaining" subtitle) appears above
a tall-blue "Optional" frame; confirm Copy's CLI token is unaffected.

### Tests for User Story 2 ⚠️ write first, confirm they FAIL

- [X] T004 [P] [US2] Failing test: `build_field_frames()` produces required-before-optional frame order, omits an empty group's frame entirely, and applies `border: solid red;`/`border: solid blue;` + correct `border_title`s — in `tests/integration/test_tui_visual_design.py`
- [X] T005 [P] [US2] Failing test: the required frame's `border_subtitle` starts at the correct count, decrements/increments as required fields are filled/cleared, and reads `"0 remaining"` once all are filled (not omitted/stale) — in `tests/integration/test_tui_visual_design.py`
- [X] T006 [P] [US2] Failing regression test: CLI tokens (Run/Copy/Copy & exit) produced by every prep screen are byte-for-byte unchanged by frame grouping (FR-007) — in `tests/integration/test_tui_visual_design.py`

### Implementation for User Story 2

- [X] T007 [US2] Add `FieldSpec` dataclass (`label: str`, `widget: Widget`, `required: bool`, `autocomplete: Widget | None = None`, `browse: Widget | None = None`) to `src/ome_zarr_tools/tui/fields.py`
- [X] T008 [US2] Add `build_field_frames(specs: list[FieldSpec]) -> list[Vertical]` to `src/ome_zarr_tools/tui/fields.py`: required frame (`border: solid red;`, `border_title="Required"`) before optional frame (`border: solid blue;`, `border_title="Optional"`); omit either frame if its group is empty (depends on T007)
- [X] T009 [US2] Add a helper computing "count of required `FieldSpec`s whose widget is currently empty" and wire the required frame's `border_subtitle` to it in/around `build_field_frames()` (depends on T008)
- [X] T010 [US2] Rewrite `CommandFormScreen.compose()` in `src/ome_zarr_tools/tui/app.py` to build one `FieldSpec` per `click.Parameter` and call `build_field_frames()` instead of the flat field loop; recompute the required subtitle from the screen's field-changed handling (depends on T007-T009)
- [X] T011 [US2] Rewrite `InspectScreen.compose()` in `src/ome_zarr_tools/tui/screens/inspect_screen.py` to build its own short `FieldSpec` list and call `build_field_frames()` (depends on T007-T009)
- [X] T012 [US2] Rewrite `FixMetadataScreen.compose()`/`MigrateScreen.compose()` in `src/ome_zarr_tools/tui/screens/metadata_screen.py` the same way (depends on T007-T009)
- [X] T013 [US2] Rewrite `ConfigScreen.compose()` in `src/ome_zarr_tools/tui/screens/config_screen.py` the same way (depends on T007-T009)
- [X] T014 [US2] Run T004-T006; confirm they now pass

**Checkpoint**: User Story 2 fully functional and independently testable.

---

## Phase 5: User Story 3 - Field labels people can read (Priority: P3)

**Goal**: Human-readable, capitalized/space-separated field labels; CLI
tokens unaffected.

**Independent Test**: Open any form; confirm labels read as words (e.g.
"Voxel Size Unit"), not `--voxel_size_unit`; confirm Copy's token still
uses the raw flag.

### Tests for User Story 3 ⚠️ write first, confirm they FAIL

- [X] T015 [P] [US3] Failing test: every `click.Parameter`-derived label renders as capitalized, space-separated text with no `--`/leading `-`/underscores — in `tests/integration/test_tui_visual_design.py`
- [X] T015a [P] [US3] Failing test: a field label too long for the frame's width wraps to a second line without truncating and without breaking the frame's border (FR-006a) — in `tests/integration/test_tui_visual_design.py`
- [X] T016 [P] [US3] Failing regression test: Copy/Copy & exit's CLI token is unaffected by label casing — in `tests/integration/test_tui_visual_design.py`

### Implementation for User Story 3

- [X] T017 [US3] Change `field_label()` in `src/ome_zarr_tools/tui/fields.py` to return `param.name.replace("_", " ").title()` instead of `param.opts[0]`/`human_readable_name`
- [X] T017a [US3] Ensure the label `Static`/`Label` widget `build_field_frames()` renders inside each frame wraps by default (no `text-wrap: nowrap`/ellipsis CSS anywhere in the chain) rather than truncating, per FR-006a; add explicit wrap CSS if Textual's default for the container doesn't already do this — in `src/ome_zarr_tools/tui/fields.py` (depends on T008, T017)
- [X] T018 [US3] Confirm the required-field marker (`" *"`) still appends after the new label text, in `CommandFormScreen` (`src/ome_zarr_tools/tui/app.py`) and every specialized screen (depends on T017, T010-T013)
- [X] T019 [US3] Confirm specialized screens' hand-written `FieldSpec` labels (`inspect_screen.py`, `metadata_screen.py`, `config_screen.py`) are already human-readable literal text (e.g. `"Zarr Path"`), adjusting any that aren't
- [X] T020 [US3] Run T015-T016 and T015a; confirm they now pass

**Checkpoint**: User Story 3 fully functional and independently testable.

---

## Phase 6: User Story 4 - Pick zarr paths without typing them (Priority: P4)

**Goal**: A 3-row Browse button beside every path field, opening a
directory-tree picker.

**Independent Test**: Open `inspect`; confirm a Browse button appears
beside `zarr_path`; press it, select an entry, confirm the field fills and
every other field is untouched; reopen and cancel, confirm no change.

### Tests for User Story 4 ⚠️ write first, confirm they FAIL

- [X] T021 [P] [US4] Failing test: every path-typed field shows a 3-row Browse button positioned right of its input — in `tests/integration/test_tui_browse_picker.py`
- [X] T021a [P] [US4] Failing test: a path field's existing typing + local-path autocomplete behavior is unaffected by the added Browse button (FR-013) — in `tests/integration/test_tui_browse_picker.py`
- [X] T022 [P] [US4] Failing test: `BrowsePickerScreen` push/dismiss round-trip — selecting an entry fills the field and leaves every other field untouched; cancel (Escape/no selection) leaves the field unchanged — in `tests/integration/test_tui_browse_picker.py`
- [X] T023 [P] [US4] Failing test: `SafeDirectoryTree.filter_paths()` enforces the field's dir/file/any constraint, and tolerates a permission-denied entry without crashing — in `tests/integration/test_tui_browse_picker.py`

### Implementation for User Story 4

- [X] T024 [US4] Create `src/ome_zarr_tools/tui/screens/browse_screen.py`: `SafeDirectoryTree(DirectoryTree)` (`filter_paths()` per `only: Literal["dir", "file", "any"]`, tolerates `PermissionError` like `SafePathAutoComplete`) and `BrowsePickerScreen(ModalScreen[Path | None])` (`dismiss(path)` on selection, `dismiss(None)` on cancel)
- [X] T025 [US4] Add a `Button("Browse", height=3)` per path-typed `FieldSpec` in `src/ome_zarr_tools/tui/fields.py`, wired to `push_screen(BrowsePickerScreen(root, only), callback)`; callback fills the field only if the result is not `None` (depends on T024, T007)
- [X] T026 [US4] Run T021-T023 and T021a; confirm they now pass

**Checkpoint**: User Story 4 fully functional and independently testable.

---

## Phase 7: User Story 5 - See remote paths as remote, not raw text (Priority: P5)

**Goal**: A provider-colored, non-editable scheme add-on for recognized
remote-path prefixes, with autocomplete suppressed while shown.

**Independent Test**: Type `gs://my-bucket/data.zarr` into a path field;
confirm a blue `gs://` add-on with only `my-bucket/data.zarr` editable, no
local autocomplete; backspace to empty, confirm the scheme reappears as
plain editable text.

### Tests for User Story 5 ⚠️ write first, confirm they FAIL

- [X] T027 [P] [US5] Failing state-machine test covering type/backspace transitions for all 4 color groups (`gs://`/`gcs://` blue, `s3://` orange, `az://`/`abfs://` cyan, `http://`/`https://` gray), including the bare-scheme-stays-plain-text edge case — in `tests/integration/test_tui_remote_addon.py`
- [X] T027a [P] [US5] Failing test: the Browse button remains positioned right of the whole field group (add-on + input), unaffected by whether the add-on is currently shown (FR-019) — in `tests/integration/test_tui_remote_addon.py`
- [X] T028 [P] [US5] Failing test: local autocomplete is disabled while an add-on is shown, re-enabled once reverted to plain text — in `tests/integration/test_tui_remote_addon.py`
- [X] T029 [P] [US5] Failing regression test: CLI token is identical between add-on state and the same value typed as plain text, for every scheme — in `tests/integration/test_tui_remote_addon.py`

### Implementation for User Story 5

- [X] T030 [US5] Add `REMOTE_SCHEME_COLORS: dict[str, str]` to `src/ome_zarr_tools/tui/fields.py`
- [X] T031 [US5] Swap a path-typed `FieldSpec`'s widget for a `Horizontal` of (optional add-on `Label`, `Input`, autocomplete, Browse button) with an `Input.Changed` handler implementing the show/hide-add-on + autocomplete-disable state machine, in `src/ome_zarr_tools/tui/fields.py` (depends on T030, T025)
- [X] T032 [US5] Update CLI-token generation to combine the add-on's scheme text (if shown) with the `Input`'s text into one token, in `src/ome_zarr_tools/tui/fields.py` (depends on T031)
- [X] T033 [US5] Run T027-T029 and T027a; confirm they now pass

**Checkpoint**: User Story 5 fully functional and independently testable.

---

## Phase 8: User Story 6 - Know what you're about to run (Priority: P6)

**Goal**: A titled, gold-bordered Command Identity frame (name +
description) at the top of every prep screen.

**Independent Test**: Open any prep screen; confirm a titled frame at the
top shows the command's name and description, matching its menu entry's
text, and is visually distinct from the red/blue field-group frames.

### Tests for User Story 6 ⚠️ write first, confirm they FAIL

- [X] T034 [P] [US6] Failing test: every prep screen shows a titled frame (`border: round #d4af37;`) above its field content with the correct command name (`border_title`) and description (`command.get_short_help_str(limit=70)`) — in `tests/integration/test_tui_visual_design.py`
- [X] T035 [P] [US6] Failing test: a command with no CLI help text still renders the identity frame with its name, description blank (not an error) — in `tests/integration/test_tui_visual_design.py`

### Implementation for User Story 6

- [X] T036 [US6] Add `build_identity_frame(command: click.Command) -> Vertical` to `src/ome_zarr_tools/tui/fields.py`: `border: round #d4af37;`, `border_title = command.name`, body `Label(command.get_short_help_str(limit=70))`. Note: User Story 7's `CommandResultScreen` (Phase 9) also calls this function directly — implement it here first.
- [X] T037 [US6] Yield `build_identity_frame(self.command)` first in `CommandFormScreen.compose()` in `src/ome_zarr_tools/tui/app.py` (depends on T036, T010)
- [X] T038 [US6] Yield the equivalent identity frame first in `InspectScreen.compose()`, `FixMetadataScreen.compose()`/`MigrateScreen.compose()`, `ConfigScreen.compose()` (depends on T036, T011-T013)
- [X] T039 [US6] Run T034-T035; confirm they now pass

**Checkpoint**: User Story 6 fully functional and independently testable.

---

## Phase 9: User Story 7 - A dedicated place to see what happened (Priority: P7)

**Goal**: Pressing Run navigates *immediately* to a per-command Result
screen (identity frame + a `StatusPanel`-driven progress indicator while
pending), which swaps to the outcome once the command finishes; plus a
Restore Defaults action that reloads a prep screen to its opening state.

**Independent Test**: Run any command; confirm `app.screen` becomes that
command's Result screen *immediately* (before the worker resolves),
showing the identity frame and a pending progress indicator; confirm it
flips to a success/failure indicator + that command's specific content
once finished; confirm "Back to form" returns to the prep screen with
fields intact from either state; confirm a blocked Run (missing required
field) navigates nowhere; confirm Restore Defaults reloads a prep screen
to its opening values.

### Tests for User Story 7 ⚠️ write first, confirm they FAIL

- [X] T040 [P] [US7] Failing test: pressing Run on a filled `CommandFormScreen` navigates `app.screen` to `GenericResultScreen` *immediately* (before the worker resolves), showing the identity frame and `StatusPanel`'s pending progress indicator (bar or sparkline); once the worker resolves successfully, that same screen instance shows a success indicator + the execution log + no extra content — in `tests/integration/test_tui_result_screen.py`
- [X] T041 [P] [US7] Failing test: same immediate-navigation check for a command that fails, and that the Result screen flips to a failure indicator + error message once the worker resolves — in `tests/integration/test_tui_result_screen.py`
- [X] T042 [P] [US7] Failing test: Run with an empty required field does not navigate anywhere (existing inline validation notification still fires) — in `tests/integration/test_tui_result_screen.py`
- [X] T043 [P] [US7] Failing test: pressing "Back to form" (footer shows that label, not `shared_bindings()`'s "Back to menu") from the Result screen, in either the pending or finished state, pops back to the exact prep-screen instance with every field value unchanged — in `tests/integration/test_tui_result_screen.py`
- [X] T043a [P] [US7] Failing test: pressing Run again while that command's Result screen is still pending re-navigates to the same instance rather than constructing a new one — in `tests/integration/test_tui_result_screen.py`
- [X] T044 [P] [US7] Failing tests: once finished, `InspectResultScreen` shows the summary/JSON report, `FixMetadataResultScreen`/`MigrateResultScreen` show the applied diff, `ConfigResultScreen` shows the written config JSON — in `tests/integration/test_tui_result_screen.py`
- [X] T044a [P] [US7] Failing test: pressing Restore Defaults (`F4`) on a prep screen with edited fields replaces `app.screen` with a fresh instance of the same class whose fields show their opening values (including non-empty defaults), and, for specialized screens, whose other live content (diff/current-config views) is likewise reset — in `tests/integration/test_tui_result_screen.py`
- [X] T044b [P] [US7] Failing test: Restore Defaults is a no-op while fields are disabled during a pending run — in `tests/integration/test_tui_result_screen.py`

### Implementation for User Story 7

- [X] T045 [US7] Create `src/ome_zarr_tools/tui/screens/result_screen.py`: `CommandResultScreen(Screen[None])` base — `compose()` yields `build_identity_frame(self.command)` first (depends on T036), then either an embedded `StatusPanel` (pending) or a success/failure `Label` + `compose_result_content()` + the same `StatusPanel` (finished); `self._finished: bool` set imperatively (not `reactive()`); `begin()` calls `status_panel.start()` and returns `(status_panel.update_progress, status_panel.append_log)`; `finish(result: ExecutionResult)` sets `_finished = True`, calls `status_panel.stop()`, re-renders the finished state; `BINDINGS = [Binding("escape", "back", "Back to form"), *shared_bindings()]` (override listed *first* — verified in research.md that Textual displays the first same-key binding's label while the action still fires once); `action_back()` -> `self.app.pop_screen()`. Plus `GenericResultScreen(CommandResultScreen)` with an empty `compose_result_content()`
- [X] T046 [US7] Rewrite `CommandFormScreen` in `src/ome_zarr_tools/tui/app.py`: `action_run()` — after existing required-field validation, if `self._pending_result` is set, `push_screen(self._pending_result)` and return (FR-025a); otherwise construct `GenericResultScreen(self.command)`, store it as `self._pending_result`, `push_screen()` it, call its `begin()`, and pass the returned callables plus an `on_done` (calls `finish(result)`, then clears `self._pending_result`) into `run_command()`. Add `action_restore_defaults()` bound to `F4`: no-op while fields are disabled, otherwise `await self.app.switch_screen(CommandFormScreen(self.command))` (depends on T045)
- [X] T047 [US7] Add `InspectResultScreen(CommandResultScreen)` (`compose_result_content()` yields the existing summary/JSON report panels) in `src/ome_zarr_tools/tui/screens/inspect_screen.py`; rewrite `InspectScreen.action_run()` the same immediate-push/`begin()`/`finish()`/pending-guard pattern as T046; add `InspectScreen.action_restore_defaults()` bound to `F4` (`await self.app.switch_screen(InspectScreen())`) (depends on T045)
- [X] T048 [US7] Add `FixMetadataResultScreen`/`MigrateResultScreen(CommandResultScreen)` (yield the diff that was applied) in `src/ome_zarr_tools/tui/screens/metadata_screen.py`; rewrite `FixMetadataScreen.action_run()`/`MigrateScreen.action_run()` the same pattern as T046; add `action_restore_defaults()` to both, bound to `F4` (depends on T045)
- [X] T049 [US7] Add `ConfigResultScreen(CommandResultScreen)` (yields the written config JSON) in `src/ome_zarr_tools/tui/screens/config_screen.py`; rewrite `ConfigScreen.action_run()` the same pattern as T046; add `ConfigScreen.action_restore_defaults()` bound to `F4` (depends on T045)
- [X] T050 [US7] Run T040-T044, T043a, T044a, T044b; confirm they now pass

**Checkpoint**: User Story 7 fully functional and independently testable — all 7 user stories complete.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T051 [P] Run the full quality gate (`ruff check src tests`, `ruff format --check src tests`, `mypy src/ome_zarr_tools`, `pytest`) and fix any fallout
- [X] T052 Update `tests/integration/test_tui_shortcuts.py`/`test_tui_structure.py` if User Story 7's navigation change requires adjusting any "stays on the same screen after Run" assertion (plan.md's Constraints flags this as the one deliberate behavior change)
- [ ] T053 Run `quickstart.md`'s manual walkthroughs end-to-end in a real terminal (`ome-zarr-tools interactive --tui`) for User Stories 2 through 7

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None — nothing to do.
- **Foundational (Phase 2)**: None — nothing blocks every story at once.
- **User Story 1 (Phase 3)**: Already complete.
- **User Stories 2-7 (Phases 4-9)**: See "User Story Dependencies" below — not all independent.
- **Polish (Phase 10)**: Depends on whichever user-story phases are done.

### User Story Dependencies

- **User Story 2 (P2)**: No dependency on other unimplemented stories. Introduces `FieldSpec`/`build_field_frames()` — the shared primitive Stories 3, 4, and 5 build on.
- **User Story 3 (P3)**: Depends on User Story 2's `FieldSpec` (its label text flows through frames built by `build_field_frames()`). Same-file edits as US2 in `app.py`/specialized screens — implement after US2, not in parallel with it.
- **User Story 4 (P4)**: Depends on User Story 2's `FieldSpec` (Browse button is attached per `FieldSpec`). Independent of US3.
- **User Story 5 (P5)**: Depends on User Story 2's `FieldSpec` and User Story 4's Browse button (the add-on `Horizontal` composition includes the Browse button). Implement after US4.
- **User Story 6 (P6)**: No conceptual dependency on `FieldSpec` (a separate `build_identity_frame(command)` function) — but edits the same `compose()` methods User Story 2 already rewrote, so implement after US2 to avoid merge churn on the same lines.
- **User Story 7 (P7)**: Depends on User Story 6's `build_identity_frame()` — `CommandResultScreen` (T045) calls it directly to build its own top block, per FR-022a's "Result screen shares the prep screen's identity frame." No dependency on `FieldSpec`/`build_field_frames()`; Restore Defaults (`switch_screen()`-based) and the Result-screen navigation/progress machinery are otherwise independent of Stories 2-5's field-building work, but each screen's `action_run()`/`action_restore_defaults()` edits (T046-T049) do land in the same files US2's `compose()` rewrites (T010-T013) touched.

**Practical consequence**: unlike a typical spec-kit feature where user stories are fully independent, Stories 2 → 3 → 4 → 5 form a dependency chain through `FieldSpec`/`build_field_frames()` and should be implemented in that order. Story 6 should follow Story 2 for the same file-churn reason. Story 7 now depends on Story 6 specifically for `build_identity_frame()` — implement it last, in priority order, rather than pulling it forward.

### Within Each User Story

- Tests MUST be written and confirmed FAILING before implementation (constitution Principle II).
- Shared primitives (`FieldSpec`, `build_field_frames`, `build_identity_frame`, `CommandResultScreen`) before the screens that consume them.
- Story's own "Run T0xx-T0yy; confirm they now pass" task last.

### Parallel Opportunities

- All test-writing tasks marked [P] within a story's Tests section can be written in parallel (different assertions, same new test file — coordinate on file edits, or split into separate test functions added independently).
- User Story 7's *test-writing* (T040-T044, T043a, T044a, T044b) can proceed in parallel with Stories 2-6, but its *implementation* needs User Story 6's `build_identity_frame()` (T036) landed first, since `CommandResultScreen` (T045) calls it directly.
- Story 6's identity-frame test-writing (T034-T035) can proceed in parallel with Story 2-5's test-writing, even though its implementation should land after Story 2's.

---

## Parallel Example: User Story 2

```bash
# Tests can be drafted together (same new file, independent assertions):
Task: "Failing test: build_field_frames() frame order/omission/border style in tests/integration/test_tui_visual_design.py"
Task: "Failing test: required frame's live border_subtitle count in tests/integration/test_tui_visual_design.py"
Task: "Failing regression test: CLI tokens unaffected by frame grouping in tests/integration/test_tui_visual_design.py"
```

---

## Implementation Strategy

### Already-shipped MVP

User Story 1 is live (`3383bb8`). The next-smallest complete increment is
User Story 2 alone (Phase 4) — it's independently testable per its own
Independent Test, and every later story either depends on it directly
(US3-US6) or can be added without touching it (US7).

### Incremental Delivery

1. User Story 2 → test independently → deploy/demo.
2. User Story 3 → test independently → deploy/demo.
3. User Story 4 → test independently → deploy/demo.
4. User Story 5 → test independently → deploy/demo.
5. User Story 6 → test independently → deploy/demo.
6. User Story 7 → test independently → deploy/demo (test-writing can start earlier per "Parallel Opportunities" above; implementation needs US6 done first).
7. Polish (Phase 10).

### Parallel Team Strategy

With two contributors: one works Stories 2 → 3 → 4 → 5 → 6 in sequence
(the `FieldSpec`-dependent chain, ending with US6's `build_identity_frame()`);
the other drafts Story 7's tests in parallel, then implements Story 7 once
US6 lands; both converge on Phase 10.

---

## Notes

- [P] tasks touch different files, or independent regions of a shared new
  test file, with no dependency on an unfinished task.
- [Story] label maps each task to its user story for traceability.
- Every implementation task cites its exact file path per `plan.md`'s
  Project Structure.
- Commit after each user-story checkpoint (T014, T020, T026, T033, T039,
  T050), per this project's Deliberate Commit Discipline (constitution
  Principle III) — new commits only, never amend.
- User Story 1's tasks are included pre-checked for a complete record;
  don't re-implement them.
