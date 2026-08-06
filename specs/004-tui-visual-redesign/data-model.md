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
list[FieldSpec]) -> list[Vertical]`, returning 1 or 2 `Vertical` containers
(`border: round`, `border_title` = `"Required"`/`"Optional"`) each
containing its specs' labels+widgets(+autocomplete/+browse), in the order
specs were given, required-frame first (per spec.md's documented
assumption).

**Relationships**: `CommandFormScreen.compose()` builds one `FieldSpec` per
`click.Parameter` and passes the list to `build_field_frames()`. Each
specialized screen (`InspectScreen`, `FixMetadataScreen`, `MigrateScreen`,
`ConfigScreen`) builds its own short, hand-written `FieldSpec` list for its
fixed fields and calls the same function.

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
composes a `SafeDirectoryTree` (a `DirectoryTree` subclass overriding
`filter_paths()` per `only`, and tolerating `PermissionError` like
`SafePathAutoComplete` already does) and dismisses with the selected
`Path`, or `None` on cancel.

**State transition**: Button pressed → modal pushed → user selects entry
(`dismiss(path)`) or cancels (`dismiss(None)`) → callback on the calling
screen sets the field's value only if the result is not `None`.

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
