# Phase 1 Data Model: TUI Visual Redesign

No persisted data entities — this is a UI-structure/rendering change to an
existing, already-implemented TUI. Spec.md's Key Entities map onto code
constructs as follows.

## Logo

**Represents**: The static ASCII-art block (Matryoshka-doll motif) shown
above the command menu's list.

**Representation**: `tui/logo.py`'s `LOGO: str` constant (the ASCII art)
and `Logo(Static)`, a thin widget wrapping it. `display` is a reactive bool
toggled by an `on_resize` handler comparing `self.size` against a minimum
width/height threshold (FR-002).

**Relationships**: Mounted once, above the `OptionList`, in
`CommandMenuScreen.compose()`. No other screen references it.

## Command Menu Entry

**Represents**: One `OptionList` row: command name (bold), the command's
existing CLI help text, and a blank spacing line — a 3-line Rich
renderable.

**Representation**: A small pure function in `app.py`,
`_menu_option_prompt(command: click.Command) -> RenderableType`, returning
a `rich.console.Group` of three `Text`/blank lines, used when constructing
each `Option(prompt, id=name)` in `CommandMenuScreen.compose()`. No new
class — `Option`'s existing `prompt` parameter already accepts this
(per `research.md`).

**Validation rule**: A command with no `help`/`short_help` renders an empty
second line rather than raising (FR-002c) — the function must tolerate
`command.help is None`.

## Field Group Frame

**Represents**: A titled, bordered container holding either all of a
screen's required fields or all of its optional fields; omitted if empty.

**Representation**: `tui/fields.py`'s `FieldSpec` dataclass (`label: str`,
`widget: Widget`, `required: bool`, `autocomplete: Widget | None = None`,
`browse: Widget | None = None`) and `build_field_frames(specs:
list[FieldSpec]) -> list[Vertical]`, returning 1 or 2 `Vertical` containers,
each containing its specs' labels+widgets(+autocomplete/+browse), in the
order specs were given, required-frame first (per spec.md's documented
assumption). Each field's widget gets `margin-bottom: 1;` (a blank line
separating it from the next field) except the last field in the group.
Both containers get `height: auto;` (sized to content rather than
expanding to fill the screen) plus a 1-character `margin`/`padding`.
The required container gets `border: solid red;`, `border_title =
"Required"`, and `border_subtitle` set to `f"{n} remaining"` (`n` = count
of required specs whose widget is currently empty); the optional
container gets `border: solid blue;`, `border_title = "Optional"`, no
subtitle.

**Relationships**: `CommandFormScreen.compose()` builds one `FieldSpec` per
`click.Parameter` and passes the list to `build_field_frames()`. Each
specialized screen (`InspectScreen`, `FixMetadataScreen`, `MigrateScreen`,
`ConfigScreen`) builds its own short, hand-written `FieldSpec` list for its
fixed fields and calls the same function. Each screen's existing
field-changed handler additionally recomputes and re-sets the required
frame's `border_subtitle` whenever a required field's value changes.

## Field Label

**Represents**: The human-readable, capitalized/space-separated text shown
next to a field.

**Representation**: For `click.Parameter`-derived fields,
`fields.py`'s `field_label()` becomes `param.name.replace("_", "
").title()` (was `param.opts[0]`/`human_readable_name`). For specialized
screens' hand-built `FieldSpec`s, the label is simply written as
human-readable literal text at the call site (e.g. `"Zarr Path"`) — no
transform needed, since these were never derived from a CLI flag string.

**Validation rule**: `widget_value_to_tokens()` (CLI-token generation)
remains keyed off `param.opts[0]`/argument value, entirely independent of
`field_label()` — this is what guarantees FR-007.

## Browse Picker

**Represents**: A 3-row button beside a path field's input; opens a
directory-tree view constrained to directories/files per the field's type,
filling the field on selection, leaving it unchanged on cancel.

**Representation**: `tui/fields.py` gains a `Button("Browse", id=f"{field_id}-browse",
classes="browse-button")` (styled `height: 3` for the "3-row" requirement)
per path-typed `FieldSpec`, wired to push
`tui/screens/browse_screen.py`'s `BrowsePickerScreen(root: Path, only:
Literal["dir", "file", "any"]) -> ModalScreen[Path | None]`. The screen
composes an `Input(str(self.root), id="root-path-input")` above the
`SafeDirectoryTree` (a `DirectoryTree` subclass overriding
`filter_paths()` per `only`, and tolerating `PermissionError` like
`SafePathAutoComplete` already does), plus a `Footer`, and dismisses with
the selected `Path`, or `None` on cancel. `on_input_submitted()` parses
the `Input`'s value as a `Path`; if it's a valid directory, re-roots both
`self.root` and the tree's `path` at it (letting the user type anywhere,
including an ancestor of the initial root, since `DirectoryTree` only
exposes its root's descendants on its own — FR-009a); otherwise it
`notify()`s an error and leaves the root unchanged. (An earlier design
used a clickable "Up" button plus a `backspace` key binding instead; the
user reported the key binding didn't fire in their real terminal —
physical Backspace sends different byte sequences across
terminals/multiplexers — so both were replaced by this editable-path
approach, which also lets the user jump directly to any path rather than
only one level at a time.) `PathField` hides its own Browse button
(`_browse_button.display = False`) for as long as the remote-path add-on
is shown, reappearing when it's removed (FR-019).

**State transition**: Button pressed → modal pushed → user selects entry
(`dismiss(path)`) or cancels (`dismiss(None)`) → callback on the calling
screen sets the field's value only if the result is not `None`.
Submitting the path `Input` (Enter) while the modal is open re-roots it
without dismissing, if the typed value is a valid directory.

## Remote Path Add-on

**Represents**: A non-editable, provider-colored prefix (blue: `gs://`/
`gcs://`; orange: `s3://`; cyan: `az://`/`abfs://`; gray: `http://`/
`https://`) shown to the left of a path field's input when its value starts
with that scheme and has additional text after it; reverts to plain
editable text when the remainder is emptied.

**Representation**: A path-typed `FieldSpec`'s widget becomes a
`Horizontal` of: an optional `Label(id=f"{field_id}-addon")` (add-on,
mounted/removed reactively, styled via one of 4 CSS classes matching the
scheme-color table), the `Input` (holding only the remainder when an
add-on is shown, the full value otherwise), its `SafePathAutoComplete` (its
`disabled` reactive toggled per add-on state), and its Browse button.
`REMOTE_SCHEME_COLORS: dict[str, str]` in `tui/fields.py` is the single
source of truth for the scheme→color table (mirrors `003`'s
`shared_bindings()` pattern: one constant, imported everywhere it's
needed).

**State transition**:
- Plain text not matching any scheme prefix (or matching a bare scheme with
  no remainder) → single `Input`, no add-on, autocomplete enabled (if
  local path field).
- Text matching `<scheme>://<something>` → add-on shown (scheme, colored),
  `Input` holds only `<something>`, autocomplete disabled.
- User deletes `Input`'s text to empty while add-on is shown → add-on
  removed, `Input`'s value becomes the bare scheme string again (plain-text
  state, autocomplete for that scheme stays disabled per spec.md's edge
  case: a bare scheme alone is still remote-recognized).

**Validation rule**: `widget_value_to_tokens()` reads the *combined* value
(add-on's scheme text, if shown, concatenated with the `Input`'s text) so
the CLI token is identical regardless of visual state (FR-007/FR-018).

## Command Identity Frame

**Represents**: A borderless block at the top of every prep screen, above
the field content, showing the command's name in bold with its existing
CLI description underneath.

**Representation**: `tui/fields.py`'s `build_identity_frame(command:
click.Command) -> Vertical`, returning one `Vertical` (`height: auto;`,
`padding: 1 2;`, no border) containing two `Label`s: `#identity-name`
(`text-style: bold;`, `command.name`) and `#identity-description`
(`width: 100%; max-height: 3;`,
`Label(command.get_short_help_str(limit=10_000))` — the same help-text
source `_menu_option_prompt()` uses, but unbounded so it is never
ellipsis-ed, just capped at 3 rendered lines).

**Relationships**: Every prep screen's `compose()`
(`CommandFormScreen`, `InspectScreen`, `FixMetadataScreen`,
`MigrateScreen`, `ConfigScreen`) yields this once, first, before its
field content (FR-020). Uses a color (gold) distinct from the Field Group
Frame's red/blue so the frame types don't visually conflate (FR-021).
`CommandResultScreen` (below) yields the *same* built frame — built from
the same `command: click.Command` reference the prep screen already has —
first in its own `compose()` too, in both its pending and finished state
(FR-022a).

**Validation rule**: A command with no CLI help text still renders the
frame with its name; the description `Label` is empty rather than raising
(same tolerance as `_menu_option_prompt`, FR-020's acceptance scenario 2).

## Command Result Screen

**Represents**: The screen the app navigates to immediately when Run is
pressed (not once the command finishes) — showing the identity frame plus
a progress indicator while pending, then a success/failure indicator plus
that command's own specific output once finished.

**Representation**: `tui/screens/result_screen.py`'s
`CommandResultScreen(Screen[None])` — a base class with two rendering
states tracked by a plain instance attribute, `self._finished: bool`
(imperatively set, not a `reactive()` — same reasoning as the required
frame's `border_subtitle`, `Widget.size` not being a `reactive()` having
already burned this feature once). `compose()` always yields
`build_identity_frame(self.command)` first, then either an embedded
`StatusPanel` instance (pending) or a success/failure `Label` +
`compose_result_content()`'s output + the same `StatusPanel` (finished,
reused for its toggleable log rather than a second log widget — see
research.md's status-panel-reuse decision). Two methods drive the
transition: `begin()` (called right after the screen is pushed) calls
`self._status_panel.start()` and returns the `on_progress`/`on_log`
callables (`self._status_panel.update_progress`/`.append_log`) for the
caller to pass into `run_in_background`/`run_command`; `finish(result:
ExecutionResult)` (the `on_done` callback) sets `self._finished = True`,
calls `self._status_panel.stop()`, and triggers a re-render showing the
outcome. `action_back()` -> `self.app.pop_screen()`, bound via a
screen-local `BINDINGS` override so its label reads "Back to form"
instead of `shared_bindings()`'s generic "Back to menu" (FR-023,
research.md's binding-override decision — verified empirically that a
same-key `Binding` listed first wins the Footer label while the action
still fires once). Subclasses implement `compose_result_content() ->
ComposeResult` for their finished-state command-specific widgets:
`GenericResultScreen` (`from_images`/`extract`/`apply_mask`, and any
command without a specialized screen) adds nothing beyond the shared log;
`InspectResultScreen` adds the existing summary/JSON report panels;
`FixMetadataResultScreen`/`MigrateResultScreen` add the diff that was
applied; `ConfigResultScreen` adds the written config JSON.

**Relationships**: Each prep screen's `action_run()` — after its existing
required-field validation (FR-025) — constructs the matching
`CommandResultScreen` subclass, `push_screen()`s it, calls its `begin()`,
and passes the returned callables into `run_in_background`/`run_command`
along with an `on_done` that calls the same screen's `finish()`. The prep
screen keeps `self._pending_result: CommandResultScreen | None` (cleared
inside `finish()`, via a callback back to the prep screen) so a second
Run press for the same still-pending command re-navigates to that
instance instead of starting a second worker (FR-025a, research.md's
duplicate-execution-guard decision). Pushed, not modal — `action_back`
pops back to the exact prep-screen instance beneath it, fields unchanged,
in either state (FR-026).

**State transition**: Run pressed (all required fields filled, no run
already pending for this command) → `CommandResultScreen` subclass
constructed and pushed *immediately*, showing the identity frame +
pending `StatusPanel` → worker thread executes, `on_progress`/`on_log`
update that same screen's `StatusPanel` → `on_done` fires on the UI
thread → `finish()` flips the screen to its finished state (success/
failure indicator + command-specific content) → user presses "Back to
form" → screen popped, prep screen (with its original field values) is
shown again. Run pressed with an empty required field never reaches the
worker thread at all (existing inline-validation short-circuit,
unchanged) — no `CommandResultScreen` is ever constructed in that case
(FR-025). Run pressed again while a Result screen for that command is
still pending re-navigates to it rather than constructing a second one
(FR-025a).

## Restore Defaults

**Represents**: A prep-screen action resetting every field (and any other
live content) to the state the screen held when it first opened.

**Representation**: A new `action_restore_defaults()` on each prep screen
(`CommandFormScreen` and each specialized screen), bound to `F4` (added to
each prep screen's own `BINDINGS`, alongside `shared_bindings()`). No-ops
while fields are `.disabled` during a run (FR-027a); otherwise calls
`await self.app.switch_screen(type(self)(self.command))` (`CommandFormScreen`,
which needs its `command` argument) or `type(self)()` (the no-arg
specialized screens) — replacing the current screen with a freshly
constructed instance of the same class. Every field's default and every
specialized screen's other live content (diff view, current-config view)
is recomputed from scratch by that instance's own `__init__`/`compose()`/
`on_mount()`, the same code path already used the first time the screen
opened — there is no separate "recorded opening value" to maintain.

**Relationships**: `CommandFormScreen` and each specialized screen
(`InspectScreen`, `FixMetadataScreen`, `MigrateScreen`, `ConfigScreen`)
each gain this binding/action independently, calling `switch_screen()`
with their own constructor signature — there is no shared
`FieldSpec`-level "opening value" concept needed, since reconstructing
the whole screen already produces correct defaults for every field.
