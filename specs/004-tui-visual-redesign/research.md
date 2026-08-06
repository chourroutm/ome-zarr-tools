# Phase 0 Research: TUI Visual Redesign

## Baseline audit

Read every screen's `compose()` (`app.py`'s `CommandMenuScreen`/
`CommandFormScreen`, and the three specialized screens) to establish what
actually needs to change.

**Findings**:

- `CommandFormScreen` (shared by `from_images`/`extract`/`apply_mask`)
  builds one widget per `click.Parameter` via `fields.py`'s
  `field_label`/`build_field_widget`/`is_required`/`build_autocomplete`,
  iterating `self.command.params` in whatever order Click declared them —
  exactly the "undifferentiated list" User Story 2 targets.
- The three specialized screens (`InspectScreen`, `FixMetadataScreen`/
  `MigrateScreen`, `ConfigScreen`) do **not** iterate `click.Parameter`s —
  each hand-builds its own small, fixed set of widgets directly (e.g.
  `InspectScreen` has exactly one field, `zarr_path`; `MigrateScreen` has
  `zarr_path` + `target_version`). User Story 2/3 (frames, labels) still
  apply to them (the spec says "generic and specialized"), but the
  mechanism can't be "iterate `command.params`" for these — it needs a
  shared primitive both paths can feed into.
- Only path-typed fields (`click.Path`) get `SafePathAutoComplete` today;
  booleans already use `Checkbox`, choices already use `Select` (per
  `is_flag`/`click.Choice` branches in `build_field_widget`) — confirms
  User Story 4/5's "other widgets" framing is specifically about path
  fields, not a wider audit (already captured as an Assumption in spec.md).
- `build_autocomplete` attaches `SafePathAutoComplete` once at `compose()`
  time with no reactive on/off switch — User Story 5's "disable
  autocomplete while in add-on state" is new dynamic behavior, not a toggle
  that already exists (already captured as an Assumption in spec.md).

## Decision: One shared `FieldSpec` + `build_field_frames()` primitive

**Decision**: Add `tui/fields.py`'s `FieldSpec` (a small dataclass: `label:
str`, `widget: Widget`, `required: bool`, `autocomplete: Widget | None`)
and `build_field_frames(specs: list[FieldSpec]) -> list[Widget]`, returning
up to two bordered `Vertical` containers (`border-title` "Required"/
"Optional"), each populated only if it has ≥1 spec, per FR-004.
`CommandFormScreen` builds one `FieldSpec` per `click.Parameter` (feeding
`field_label`'s new human-readable output, `is_required`, etc.); each
specialized screen builds its own short, hand-written list of `FieldSpec`s
for its fixed fields, using an already-human-readable literal label instead
of a derived one. Both paths call the same `build_field_frames()`.

**Rationale**: Textual's own layout guide (design-a-layout how-to)
recommends composing complex layouts from small, purpose-built containers
rather than ad hoc per-screen CSS; a single shared frame-builder is the
direct analogue of `003`'s `shared_bindings()` — it turns "5 screens must
independently remember to group fields the same way" into "5 screens supply
data to one function," satisfying FR-003/FR-004 by construction rather than
by convention. Sized to the concrete, present duplication (5 screens, one
grouping rule), not a speculative abstraction.

**Alternatives considered**: A shared base `Screen` subclass owning
`compose()` entirely — rejected, same reasoning as `003`'s research.md: the
five screens' non-field content (diff view, JSON panels, config editor)
differs enough that unifying `compose()` itself would be a much larger
refactor than this feature needs.

## Decision: Field label casing is a pure string transform

**Decision**: `field_label()` for `click.Parameter`-derived fields becomes
`param.name.replace("_", " ").title()` (falling back to the same for
`click.Argument`s, replacing today's `param.opts[0]`/`human_readable_name`).
Specialized screens' hand-written `FieldSpec.label` strings are already
literal, human-readable text (e.g. `"Zarr Path"`) — no transform needed
there, just no longer writing CLI-flag-shaped strings.

**Rationale**: `param.name` (e.g. `"voxel_size_unit"`) is already the
underlying Python identifier Click derives its flag from — deriving the
display label from it, rather than `param.opts[0]` (`"--voxel_size_unit"`),
is the minimal change satisfying FR-005 without touching
`widget_value_to_tokens()` (which still uses `param.opts[0]` for the actual
CLI flag, per FR-007).

## Decision: ASCII logo as a static `Static` widget, resize-reactive visibility

**Decision**: A new `tui/logo.py` module holds the Matryoshka-doll ASCII art
as a constant string and a small `Logo(Static)` widget. `CommandMenuScreen`
mounts it above the `OptionList`; an `on_resize` handler (or a CSS
`min-width`/`min-height` container query, per Textual's design-a-layout
how-to's recommendation to use docking + `fr` units rather than manual
measurement where possible) toggles `Logo.display` per FR-002.

**Rationale**: Matches the how-to's "outside-in" layout approach (fixed
elements first) and its explicit guidance to prefer CSS-driven
sizing/visibility over imperative layout code.

## Decision: `OptionList` with a Rich-renderable, 3-line `Option` prompt

**Decision**: Confirmed via Textual's own `OptionList` docs: `Option`'s
`prompt` accepts any Rich renderable, explicitly including multi-line
content ("the prompts for the options can be Rich renderables, this means
they can be any height you wish"), with a documented example rendering a
`rich.table.Table` per option. `CommandMenuScreen` builds each `Option`'s
prompt as a small Rich `Group`/`Text` combination: line 1 the command name
(styled bold), line 2 the command's `click.Command.help` (or `short_help`),
line 3 blank — satisfying FR-002a/FR-002c without a custom widget.

**Rationale**: Directly satisfies the user's explicit direction ("use the
OptionList widget with a Rich content") using `OptionList`'s documented,
built-in capability — no custom `ListView`/card widget needed.

## Decision: Header clock via `Header(show_clock=True)`

**Decision**: Every screen's `Header()` call becomes `Header(show_clock=True)`.

**Rationale**: This is a built-in Textual `Header` constructor parameter —
zero custom code satisfies FR-002d exactly.

## Decision: Browse picker as a `ModalScreen[Path | None]`

**Decision**: New `tui/screens/browse_screen.py`'s `BrowsePickerScreen`
extends `ModalScreen[Path | None]`, composing a `SafeDirectoryTree`
(a `DirectoryTree` subclass tolerating `PermissionError` the same way
`SafePathAutoComplete` already does, per the existing precedent in
`tui/fields.py`) rooted at the field's current-value's parent directory (or
cwd). `on_directory_tree_file_selected`/`on_directory_tree_directory_selected`
call `self.dismiss(path)`; an Escape/Cancel action calls `self.dismiss(None)`.
The field's Browse button handler does
`self.app.push_screen(BrowsePickerScreen(root, only=...), callback)`, where
the callback fills the field only if the result isn't `None` — leaving
every other field untouched by construction (the calling screen's state was
never part of the modal's own state).

**Rationale**: Confirmed via Textual's own screens guide: `ModalScreen[T]`
+ `dismiss(value)` + `push_screen(screen, callback)` is the documented
pattern for exactly this "collect a value, return to caller without
disturbing its state" interaction (FR-010). `DirectoryTree`'s documented
`filter_paths()` override hook is the mechanism for FR-011's dir-only/
file-only constraint (filtering to `Path.is_dir()` or excluding
directories from the *selectable* set, depending on the field's
`click.Path(file_okay=..., dir_okay=...)`).

**Alternatives considered**: A non-modal, in-place expansion of the form
(replacing the field row with an inline tree) — rejected: more invasive to
every screen's layout, and loses the "leaves everything else untouched"
guarantee `ModalScreen`'s stack-based isolation gives for free.

## Decision: Remote-path add-on as a small `Horizontal` swap, not a custom Input subclass

**Decision**: A path field's widget becomes a small composed unit: a
`Horizontal` containing (conditionally) a non-editable, colored `Label`
add-on, then the `Input` holding only the remainder text, then
(conditionally) the Browse button. An `Input.Changed` handler re-evaluates
the field's *full* logical value (add-on prefix, if shown, + the `Input`'s
own text) against the scheme table (FR-014/FR-015) on every keystroke and
toggles the add-on `Label`'s presence/text/color and the `Input`'s own
autocomplete (`SafePathAutoComplete.disabled`, per `PathAutoComplete`
supporting a `disabled` flag) accordingly. `widget_value_to_tokens()` reads
the *combined* value (add-on prefix, if present, joined with the `Input`'s
text) so FR-007/FR-018's "CLI token unaffected" holds regardless of which
visual state the field is in.

**Rationale**: Keeps `Input`'s own well-tested text-editing behavior
untouched (no need to reimplement cursor/selection handling in a custom
widget) — only what's *around* it changes. Matches Bootstrap's own
input-group pattern the user referenced: a prepended, non-form-part label
next to a real input, not a single fused widget.

**Alternatives considered**: A custom `Input` subclass overriding rendering
to draw the prefix inline (like a placeholder) — rejected: `Input` doesn't
support a non-editable leading segment natively, and reimplementing
cursor-position math to keep it non-editable would be substantially more
code than composing a `Label` + `Input` pair.

## Testing approach

Unchanged from `002`/`003`: `pytest` + `pytest-asyncio` via Textual's
`App.run_test()`/`Pilot`. New coverage needed: `ModalScreen` push/dismiss
round-trips (`pilot.pause()` after `push_screen`, then simulate a
`DirectoryTree` selection message), the add-on swap's `Input.Changed`
reactivity (type/backspace sequences via `pilot.press(*"...")`), and static
assertions on `Option.prompt`'s Rich content (line count, text content) for
the 3-line menu entries — mirroring `003`'s static `BINDINGS`-inspection
test style where a full render isn't needed to prove the invariant.
