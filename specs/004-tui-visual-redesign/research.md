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

## Decision: Frame border style/color and a live required-count subtitle

**Decision**: `build_field_frames()`'s required-fields `Vertical` gets
`border: solid red;` and its optional-fields `Vertical` gets
`border: solid blue;` (per-container CSS, not a shared class, since the two
frames need different colors) — `tall` and the named colors `red`/`blue`
are confirmed built-in Textual border-edge/color values (checked directly
against the installed `textual` package: `tall` is one of
`textual._border.BORDER_CHARS`'s keys; `Color.parse("red")`/`Color.parse
("blue")` both resolve). The required frame's `border_subtitle` (a plain
settable string property on every `Widget`, confirmed via
`Widget.__dict__["border_subtitle"]` — a `_BorderTitle` descriptor, not a
`reactive()`, so there is nothing to `watch()`; it must be set
imperatively) is computed as `f"{n} remaining"` where `n` is the count of
required `FieldSpec`s whose widget currently has no value, recomputed by
`CommandFormScreen`/each specialized screen's own field-changed handler
(the same handler each screen already uses to drive its live preview/diff)
every time a required field's value changes.

**Rationale**: Directly satisfies FR-004a/FR-004b as the user specified
them ("solid red"/"solid blue" border styles, a subtitle showing the
still-empty count) using Textual's own built-in border/label mechanics —
no custom border-drawing or extra widget needed. Recomputing from each
screen's existing change handler (rather than adding a new polling/timer
mechanism) follows the same "reuse the mechanism already there" reasoning
as `002`'s live-preview decision.

**Alternatives considered**: A `reactive(int)` field-count on
`build_field_frames()`'s returned container, auto-recomputed via
`watch_children`/mount events — rejected: `Widget.size`'s equivalent
footgun from this feature's Logo work (a property that looks reactive but
isn't) argues for the simpler, explicit imperative update triggered from
the one place field values actually change, rather than a reactive
mechanism that would need its own verification.

## Decision: Command Identity Frame as a small shared builder, reusing the menu's help-text source

**Decision**: New `tui/fields.py` function `build_identity_frame(command:
click.Command) -> Vertical` returns one borderless `Vertical` container
(`padding: 1 2;`, sized to its content) holding two `Label`s: the command
name (`text-style: bold;`) and, underneath it, the description —
`Label(command.get_short_help_str(limit=10_000))`, the same source
`_menu_option_prompt()` uses for the menu's line 2 (FR-002c's
never-duplicated-copy rule extended to FR-020), with an effectively
unbounded limit so it's never ellipsis-ed, but `max-height: 3;` so a long
description is capped rather than pushing the rest of the screen down.
Every prep screen's `compose()` yields this once, first, before
`build_field_frames()`'s output.

**Rationale**: Removing the border/title (per explicit user direction)
already satisfies FR-021's "visually distinguishable from the solid
red/solid blue field frames" — a borderless block reads as clearly
different from a bordered one without needing a fourth arbitrary color.
Reusing `get_short_help_str` rather than `command.help` keeps it
consistent with the one-line-of-description convention already
established for menu entries, rather than introducing a second,
longer-form description source.

**Alternatives considered**: Folding the identity into
`build_field_frames()` as a third optional frame — rejected: identity
isn't a field group, and it would force every call site to also pass the
`click.Command` into a function whose contract today is specifically
"build frames from `FieldSpec`s."

## Decision: `CommandResultScreen` base class + per-command subclasses, triggered from each screen's existing completion callback

**Decision**: New `tui/screens/result_screen.py`'s
`CommandResultScreen(Screen[None])` is a base class (not directly
instantiated) providing: `Header()`/`Footer()` (the `003` skeleton), a
success/failure `Label` (styled green/red from the `ExecutionResult` it's
constructed with), a `RichLog` populated from the prep screen's
accumulated `on_log` lines (the same log every screen's `StatusPanel`
already captures via `run_in_background`/`run_command`'s `on_log`
parameter — `execution.py`'s existing mechanism, no new capture needed),
and `action_back()` calling `self.app.pop_screen()` — since the screen is
*pushed* on top of its prep screen (not modal), popping it returns to that
exact prep-screen instance with its fields untouched (FR-026). It reuses
`shared_bindings()` unchanged (same escape/"Back to menu" label as every
other screen) rather than inventing a Result-specific label — `003`'s
shortcut-contract already fixed that label as non-varying per screen, and
one pop of the stack still moves the user back toward the menu either way.
Subclasses override one method, `compose_result_content() ->
ComposeResult`, for their command-specific widgets:
`GenericResultScreen` (used by `from_images`/`extract`/`apply_mask`, and
any future command without a specialized screen) yields nothing extra —
the shared log already covers it; `InspectResultScreen` yields the
existing summary/JSON report panels (reusing `build_report`/`format_text`,
already called at Run time); `FixMetadataResultScreen`/
`MigrateResultScreen` yield the diff view that was actually applied
(reusing `render_diff`); `ConfigResultScreen` yields the written config
JSON. Each prep screen's existing execution-completion callback
(`CommandFormScreen._on_execution_done`, and each specialized screen's
own) additionally does `self.app.push_screen(<ResultScreenSubclass>(...))`
after its current notify/log-append logic, passing the `ExecutionResult`
and whatever command-specific content it already has in hand.

**Rationale**: Mirrors this project's own established "one shared
primitive over N independently-reimplemented screens" pattern (`003`'s
`shared_bindings()`, this feature's `build_field_frames()`); `Screen`
subclassing (rather than a shared mixin/function) fits here specifically
because the differences are in *what's composed*, not a small data
transform. Triggering from each screen's existing completion callback
reuses the exact place execution success/failure and any command-specific
result data are already computed, with no new plumbing between the worker
thread and the screen — `execution.py`'s `on_done`/`on_log` callbacks are
untouched.

**Alternatives considered**: A single concrete `CommandResultScreen` with
a `content: Widget | None` constructor parameter instead of subclassing —
rejected: `inspect`'s result needs its existing switchable
summary/JSON-panel structure (`InspectScreen`'s own F9 toggle), which is
compose-time structure, not a single drop-in widget; subclassing also
keeps each specialized command's Result variant next to its own prep
screen file (`inspect_screen.py`, `metadata_screen.py`, `config_screen.py`),
following this codebase's existing one-file-per-command-family layout. A
`ModalScreen` instead of a pushed `Screen` — rejected: modals are for
transient collect-a-value interactions (this feature's own Browse picker),
not a full-page destination the user is meant to read and navigate freely
within, per Textual's screen-vs-modal guidance already applied to the
Browse-picker decision above.

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

## Decision: Result screen navigates immediately on Run, reusing `StatusPanel` for its pending state

**Decision**: `CommandResultScreen` gains two rendering states driven by a
single `bool` reactive-ish flag (`self._finished`, set imperatively, same
reasoning as the required-frame subtitle's own imperative update): a
**pending** state (the command-identity frame + a mounted `StatusPanel`
instance) and a **finished** state (the identity frame stays; `StatusPanel`
is stopped and hidden; a success/failure `Label` + the command-specific
content per `compose_result_content()` are shown instead). Each prep
screen's `action_run()` now, after client-side validation passes:
constructs the `CommandResultScreen` subclass immediately, calls
`self.app.push_screen(result_screen)`, then calls `result_screen.begin()`
which calls its embedded `StatusPanel.start()` and kicks off
`run_in_background`/`run_command` with `on_progress=status_panel.
update_progress`, `on_log=status_panel.append_log`, and `on_done` pointed
at `result_screen.finish(result)` — i.e. the worker's callbacks now target
the newly-pushed screen's own widgets, not the prep screen's.
`tui/status.py`'s existing `StatusPanel` (confirmed by reading the source:
already exactly "progress bar once quantifiable, animated sparkline before
then, toggleable log," from spec 002 US5) is reused wholesale, mounted
inside `CommandResultScreen` rather than reimplemented — it already has
every method (`start`/`stop`/`update_progress`/`append_log`/`toggle_log`)
this feature needs.

**Rationale**: Directly satisfies FR-022/FR-022b/FR-022c using a widget
that already exists and is already tested (spec 002), rather than building
a second progress-indicator implementation. Keeping the trigger inside the
prep screen's existing `action_run()` (rather than moving execution-kickoff
logic into `CommandResultScreen` itself) means `execution.py` needs zero
changes — `run_in_background`'s callbacks were always just plain callables,
never tied to "the calling screen."

**Alternatives considered**: Keep navigation at completion (today's design)
and add a separate transient "Running..." screen shown only during
execution — rejected: two new screen classes instead of one, and it
contradicts the user's explicit framing ("on the command result page, add
a progress bar... until the results is ready") that this *is* the Result
screen's own pending state, not a distinct screen. Driving progress from
inside `CommandResultScreen.on_mount()` instead of the prep screen's
`action_run()` — rejected: the prep screen already owns required-field
validation (FR-025) and must decide *not* to navigate at all when
validation fails, so it has to run first regardless; splitting "decide
whether to run" and "start running" across two screens would need extra
back-and-forth for no benefit.

## Decision: Guard against a second execution while a Result screen is pending

**Decision**: The prep screen keeps a `self._pending_result: CommandResultScreen | None` reference, set when Run pushes a new Result screen and cleared when that screen's `finish()` is called. `action_run()`'s first check (after required-field validation) is: if `self._pending_result is not None`, `push_screen(self._pending_result)` (re-show the existing one) and return — never starting a second worker.

**Rationale**: `execution.py`'s `run_in_background` already calls `app.run_worker(_work, thread=True, exclusive=True)` — a second call while one is in flight would silently cancel the first (verified by reading `execution.py`), which combined with immediate navigation could otherwise orphan a Result screen waiting forever for an `on_done` that will never fire. Re-navigating to the same instance is the only option that can't produce that dangling state.

**Alternatives considered**: Disable the Run binding entirely while pending — rejected: `shared_bindings()` bindings aren't currently gated by any per-instance disabled state (only individual field widgets are `.disabled`), and the Result screen is what the user is actually looking at during a pending run anyway (they'd have had to explicitly navigate back to even attempt a second Run), so a soft re-navigate is simpler than adding a new binding-enablement mechanism.

## Decision: Restore Defaults reloads the prep screen via `App.switch_screen()`

**Decision**: `action_restore_defaults()` (bound to `F4`, added to each prep
screen's `BINDINGS` alongside `shared_bindings()`) is `async def
action_restore_defaults(self) -> None: if <fields disabled>: return;
await self.app.switch_screen(type(self)(self.command))` for
`CommandFormScreen` (constructor needs `command`), or `type(self)()` for
the no-arg specialized screens. Per the user's explicit direction
("restore defaults... can be done by reloading the command prep screen"),
this replaces this feature's earlier "record each field's opening value,
write it back" design entirely.

Two things were verified directly against the installed `textual`
package before committing to this, since the first thing tried
(`Widget.recompose()`, which "removes children and calls `self.compose`
again") turned out to be the *wrong* primitive for this: a screen's
`compose()` methods in this codebase mostly `yield` **already-constructed**
widget instances cached on `self` in `__init__` (e.g.
`CommandFormScreen._field_widgets`, `FixMetadataScreen._path_input`) —
`recompose()` re-mounts those same mutated instances, so a value changed
by the user survives it unchanged (confirmed: a `Static`'s value edited
before `recompose()` was still the edited value after). `App.switch_screen
(new_screen)` — "replacing the top of the screen stack with a new
screen" — was the right primitive instead: it discards the *entire old
Screen object* (and every widget instance cached on it) in favor of a
brand-new one built by a fresh `__init__()`/`compose()` call, confirmed to
replace the top of the stack without growing it (`len(app.screen_stack)`
unchanged across a `switch_screen()` call) and confirmed to actually
restore an edited widget's value back to its constructor default.

**Rationale**: A fresh instance recomputes every field's default through
the *exact* code path already used the first time the screen opened —
there is structurally only one place "what's the default" is computed,
so FR-027's "including a non-empty default" guarantee holds by
construction, with no second value-tracking mechanism to keep in sync.
As a side effect, it also resets each specialized screen's non-field
content (diff views, current-config view) for free, since those are
recomputed in `__init__`/`on_mount()` too — a strictly more complete
"restore" than the per-field write-back design would have given.

**Alternatives considered**: `Widget.recompose()` — tried first, rejected
per the empirical check above: it doesn't discard the screen's own
cached widget instances, so mutated values survive it unless every
prep screen's `compose()` were rewritten to construct fresh widgets per
call (a much larger change than the user's own "reloading" framing
implies). Recording and writing back each field's opening value
(this feature's own earlier design, superseded here) — rejected in favor
of the simpler, drift-proof, explicitly-requested reload approach.

## Decision: `CommandResultScreen`'s return binding overrides `shared_bindings()`'s label

**Decision**: `CommandResultScreen`'s `BINDINGS` is
`[Binding("escape", "back", "Back to form"), *shared_bindings()]` — the
override listed **first**. Verified directly (not assumed): when two
`Binding`s share a key within one screen's `BINDINGS`, Textual's `Footer`
displays only the *first* one for that key, while the *action* still
fires exactly once regardless of how many bindings share the key (checked
both empirically — a duplicate-`escape`-key screen rendered via
`export_screenshot()` showed only the first binding's label, and a
`pilot.press("escape")` call recorded exactly one `action_back()` call).
So listing the override before `*shared_bindings()`'s own `escape` entry
keeps `escape`'s key and `action_back` name identical to every other
screen while only changing its displayed Footer label — `shared_bindings
()` itself needs no changes.

**Rationale**: Directly implements the user's explicit ask for a clearer
name than "return to command prep." "Back to form" is unambiguous about
the destination, unlike the generic "Back to menu" label everywhere else,
which was already flagged as a slight inaccuracy for this exact screen in
this feature's earlier research (US7's original design).

**Alternatives considered**: Changing `shared_bindings()`'s signature to
accept an `escape_label` parameter, mirroring `primary_label` — rejected:
would let *every* screen vary this label, reopening exactly the
inconsistency `003`'s shortcut-contract was written to prevent; a
screen-local `BINDINGS`-order override is a smaller, more contained
deviation, scoped to the one screen where it's actually needed, and
requires no change to the shared function every other screen calls.

## Testing approach

Unchanged from `002`/`003`: `pytest` + `pytest-asyncio` via Textual's
`App.run_test()`/`Pilot`. New coverage needed: `ModalScreen` push/dismiss
round-trips (`pilot.pause()` after `push_screen`, then simulate a
`DirectoryTree` selection message), the add-on swap's `Input.Changed`
reactivity (type/backspace sequences via `pilot.press(*"...")`), static
assertions on `Option.prompt`'s Rich content (line count, text content) for
the 3-line menu entries, and — new this round — asserting `app.screen`'s
identity/class immediately after `pilot.press("f5")` (before the worker
resolves) to prove navigation truly happens at Run-press rather than at
completion, plus a subsequent `pilot.pause()` past the (test-only,
synchronous or short-sleep) worker to assert the same screen instance
flips from pending to finished content.
