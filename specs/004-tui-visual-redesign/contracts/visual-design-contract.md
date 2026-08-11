# Contract: TUI Visual Design Tokens

The concrete, testable values behind spec.md's FRs — the single source of
truth tests and future screens check against, so the redesign doesn't drift
back into per-screen one-offs (the same reasoning as `003`'s
`shortcut-contract.md`).

## Command menu (User Story 1)

| Element | Rule |
|---|---|
| Logo | Static ASCII art, Matryoshka-doll motif, shown above the `OptionList`. Hidden (not clipped) below a minimum terminal size. |
| Menu entry | 3-line Rich `Option` prompt: line 1 = command name (bold), line 2 = `command.help`/`short_help` (blank if none), line 3 = blank spacer. Line 2's `Text` is never character-truncated with an ellipsis — the full description, clipped visually at render time via `no_wrap=True, overflow="crop"` rather than a hard `limit=N` cutoff. |

## Field group frames (User Story 2)

| Element | Rule |
|---|---|
| Order | Required frame before Optional frame. Empty group → that frame is omitted entirely. |
| Border | Required frame: `border: solid red;`. Optional frame: `border: solid blue;`. |
| Title | `border_title = "Required"` / `"Optional"`, exact strings, so tests can assert on them. |
| Subtitle | Required frame only: `border_subtitle = f"{n} remaining"`, `n` = count of required fields currently empty. Recomputed on every required-field value change, including reaching `"0 remaining"`. Optional frame: no subtitle. |
| Sizing | `height: auto;` (sized to content, never expands to fill the screen) plus `margin: 1;`/`padding: 1;` (1 character on every side), on both frames. |
| Field spacing | Each field's widget gets `fields.py`'s `.field-gap` CSS class (`FIELD_GAP_CLASS`/`FIELD_GAP_CSS`, `margin-bottom: 1;`) except the last field in the group, so fields read as visually separate without a trailing gap before the frame's own bottom padding. Shared, not per-frame-type: `fix_metadata`'s Confirm screen's Prompts window (User Story 8) reuses this exact same CSS class for its own fields. |

## Field labels (User Story 3)

| Rule |
|---|
| `click.Parameter`-derived labels: `param.name.replace("_", " ").title()`. |
| Specialized-screen hand-built labels: already-human-readable literal text at the call site. |
| No per-field required marker — required-ness is conveyed by the "Required" field-group frame (above) alone, not decorated onto individual labels. |
| CLI token generation (`widget_value_to_tokens`) is entirely independent of label text — never derived from it. |

## Browse picker (User Story 4)

| Element | Rule |
|---|---|
| Button | Every path-typed field: `Button("Browse", ...)`, `height: 3`, positioned to the right of the input (and, when present, to the right of the remote-path add-on); hidden while the remote-path add-on (User Story 5) is shown (FR-019). |
| Picker | `ModalScreen[Path \| None]`, rooted at the field's current value's parent dir (or cwd). An editable `Input` (`#root-path-input`, above the tree, pre-filled with the current root) lets the user type any path and re-root the tree at it on submit (Enter) — including an ancestor of the initial root, since `DirectoryTree` only shows a root's descendants on its own. A submitted value that isn't a valid directory is rejected (error `notify()`, root unchanged). |
| Constraint | `only="dir" \| "file" \| "any"`, derived from the field's `click.Path(dir_okay=..., file_okay=...)`, enforced via `DirectoryTree.filter_paths()`. |
| Cancel | Dismiss with `None` → field unchanged. Select → field set to the chosen `Path`, every other field untouched. |

## Remote path add-on (User Story 5)

| Scheme(s) | Color |
|---|---|
| `gs://`, `gcs://` | blue |
| `s3://` | orange |
| `az://`, `abfs://` | cyan |
| `http://`, `https://` | gray |

| Rule |
|---|
| Add-on shown only when the field's value starts with a recognized scheme **and** has ≥1 character after it. |
| Bare scheme alone (e.g. exactly `"gs://"`) → plain editable text, no add-on. |
| Add-on shown → local-filesystem autocomplete disabled for that field. |
| Deleting the `Input`'s text to empty while an add-on is shown → add-on removed, `Input`'s text becomes the bare scheme string. |
| Sizing/background: `height: 3;`, `padding: 0 2;`, `background: $surface;`, and `border: tall $border-blurred;` — all matching the `Input`'s own unfocused styling exactly, so the two read as one continuous box rather than a thin `Input` beside a visually heavier solid block. `content-align: left middle;` keeps the scheme text on the same row as the `Input`'s own text. |
| CLI token = add-on's scheme text (if shown) + `Input`'s text, always — identical to the same full string typed into a plain field. |

## Command identity frame (User Story 6)

| Element | Rule |
|---|---|
| Placement | Yielded first in every prep screen's `compose()`, above the field content. |
| Border | None — borderless, `height: auto;`, `padding: 1 2;` (1 top/bottom, 2 left/right) — distinct from the field-group frames' solid red/solid blue borders. |
| Name | A `Label` (`#identity-name`, `text-style: bold;`), `command.name`. |
| Description | A `Label` (`#identity-description`, `width: 100%; max-height: 3;`) underneath the name, `command.get_short_help_str(limit=10_000)` — same source as the menu entry's line 2 (FR-002c) but unbounded, so it is never ellipsis-ed even when the menu's 70-char teaser would truncate it; capped at 3 rendered lines regardless of length; blank, not an error, for a command with no help text. |

## Command result screen (User Story 7)

| Element | Rule |
|---|---|
| Trigger | Constructed and `push_screen()`-ed from `action_run()` *immediately* once required-field validation passes (FR-022) — not after the command finishes. Never constructed when Run is blocked by that validation (FR-025). A second Run press while that command's Result screen is still pending re-navigates to the existing instance rather than constructing a new one (FR-025a). |
| Base class | `tui/screens/result_screen.py`'s `CommandResultScreen(Screen[None])` — yields the same `build_identity_frame(command)` as the prep screen (FR-022a), first, in both states. Pending state: an embedded `StatusPanel` (progress bar/sparkline, started via `begin()`). Finished state (after `finish(result)`): a success/failure `Label` + `compose_result_content()`'s output + the same `StatusPanel` (stopped, its log still toggleable). `BINDINGS` overrides `escape`'s label to "Back to form" by listing it before `*shared_bindings()` (same key, key/action unchanged, only the displayed label differs — verified empirically, see research.md). |
| Subclass content | `compose_result_content()` override per command, shown only once finished: `GenericResultScreen` (from_images/extract/apply_mask) — none beyond the shared `StatusPanel` log; `InspectResultScreen` — summary/JSON report panels; `FixMetadataResultScreen`/`MigrateResultScreen` — the applied diff, as the side-by-side panels (User Story 8, FR-035); `ConfigResultScreen` — the written config JSON. |
| Back to form | Pops the Result screen off the stack, returning to the exact prep-screen instance beneath it with every field value unchanged, from either the pending or finished state (FR-026). For `fix_metadata`/`migrate`, that "prep-screen instance beneath it" is the Confirm screen (User Story 8), not the Form screen — Confirm is what pushed the Result screen. |

## Command Confirm screen (User Story 8)

| Element | Rule |
|---|---|
| Trigger | `fix_metadata`'s/`migrate`'s Form screens' `action_run()` no longer executes (FR-028) — after required-field validation, it constructs and `push_screen()`s the matching Confirm screen instead (FR-029). No other command's Form screen is affected. |
| Base | `tui/screens/metadata_screen.py`'s `_BaseConfirmScreen(Screen[None])` — `build_identity_frame(command)`, a disabled `Input(id="confirm-path")` (FR-030), and the same bottom-bar template (`StatusPanel` + `Footer`). `BINDINGS = [Binding("escape", "back", "Back to form"), *shared_bindings(primary_label="Confirm")]` — same first-binding-wins label-override technique as the Result screen. |
| Auto mode (`migrate`) | `MigrateConfirmScreen`: either an "already at target version" message (no diff, Confirm is a no-op) or the side-by-side diff of current vs. migrated attrs (FR-031). No Restore Defaults binding — nothing is editable here. |
| Interactive mode (`fix_metadata`) | `FixMetadataConfirmScreen`: a window titled "Prompts (fix_metadata)", styled to mirror the Required field-group frame's border style/spacing (`border: solid; margin: 1; padding: 1; height: auto;`) but in green rather than red, to stay visually distinct while still reading as "the same kind of thing." The blank-line spacing between its 4 fields (all but the last) reuses `fields.py`'s shared `.field-gap` CSS class — the exact same rule the Required frame's own fields use (`FIELD_GAP_CSS`), not a separately maintained copy — pre-filled via `compute_default_prompt_values()` — the same function the CLI's own prompts use — plus a live side-by-side diff below that updates on every field edit (FR-032). Overflow (a tall window, or a tall diff) is handled by the Confirm screen's own outer `VerticalScroll`, not a nested independently-scrollable region. `F4` Restore Defaults resets the 4 fields and the diff (FR-032a), independent of the Form screen's own Restore Defaults. |
| Confirm action | `F5`, relabeled "Confirm". Validates first for `fix_metadata` (voxel size must parse as 3 numbers; blocks with an inline error otherwise) and is a no-op for `migrate` while nothing-to-do; otherwise disables what's editable, `push_screen()`s the existing Result screen, and executes (`write_metadata`/`apply_migration`) via `run_in_background`, exactly as a prep screen's Run used to (FR-033). |
| Pending guard | Same re-navigate-instead-of-double-run guard as prep screens (`self._pending_result`), since Confirm is now where execution happens. |
| Back | `escape` pops back to the exact Form-screen instance beneath, every field value unchanged (FR-034). |

## Side-by-side diff (User Story 8)

| Element | Rule |
|---|---|
| Builder | `tui/diff.py`'s `build_side_by_side_diff(before, after) -> Horizontal` — two `Static` panels (`#diff-current`/`#diff-proposed`, `border_title = "Current"`/`"Proposed"`), each pretty-printed JSON, `width: 1fr;` each. |
| Highlighting | `difflib.SequenceMatcher` opcodes: non-`"equal"` lines styled red on the left, styled green on the right; `"equal"` lines unstyled on both. |
| Line alignment | Each opcode block pads the shorter side with blank lines up to `max(len(before_block), len(after_block))`, so both panels always have the same total line count and an `"equal"` block after a `"replace"`/`"insert"`/`"delete"` lands on the same row in both panels rather than drifting apart. |
| Sizing | The outer `Horizontal` (`#side-by-side-diff`) and both panels get explicit `height: auto;` — `Horizontal`/`Vertical` default to `height: 1fr; overflow: hidden hidden;`, which silently clipped a diff taller than its container instead of letting the enclosing screen's own scroll region reach the rest of it (found and fixed alongside this feature; `#confirm-diff`/`#result-content`, the `Vertical`s hosting this widget on the Confirm and Result screens respectively, needed the same explicit `height: auto;` fix). `margin: 0 1;` on the outer `Horizontal` gives the `Current` panel the same left margin as the `Proposed` panel's right margin. |
| Used by | `MigrateConfirmScreen`'s/`FixMetadataConfirmScreen`'s diff area, and `FixMetadataResultScreen`'s/`MigrateResultScreen`'s `compose_result_content()` — replacing the single unified diff log (`tui/diff.py`'s old `diff_lines`/`render_diff`, removed) those Result screens previously used (FR-035). |

## Restore Defaults (User Story 7)

| Element | Rule |
|---|---|
| Binding | `F4`, added to each prep screen's own `BINDINGS` alongside `shared_bindings()`. |
| Behavior | `await self.app.switch_screen(type(self)(...))` — replaces the current prep screen with a freshly constructed instance of the same class, resetting every field (and any other live content) to what the screen showed on first open (FR-027). Not a per-field value write-back. |
| Disabled state | No-op while fields are disabled for the duration of a run (FR-027a). |

## Who implements this contract

- `tui/logo.py` — `Logo`, `LOGO`
- `tui/app.py` — `CommandMenuScreen` (menu entries, logo),
  `CommandFormScreen` (frames, labels, add-on, browse, identity frame,
  `action_restore_defaults()` — via `fields.py`; `action_run()` pushes
  `GenericResultScreen` immediately and drives it via `begin()`/`finish()`)
- `tui/fields.py` — `FieldSpec`, `build_field_frames`, `build_identity_frame`,
  `field_label`, `REMOTE_SCHEME_COLORS`, add-on `Horizontal` composition,
  Browse button
- `tui/screens/browse_screen.py` — `BrowsePickerScreen`, `SafeDirectoryTree`
- `tui/screens/result_screen.py` — `CommandResultScreen` (base: identity
  frame, `StatusPanel`-driven pending/finished states, `begin()`/
  `finish()`, "Back to form" binding override), `GenericResultScreen`
- `tui/screens/inspect_screen.py`, `metadata_screen.py`, `config_screen.py`
  — each screen's own `FieldSpec` list + `build_field_frames()` call,
  human-readable labels, identity frame, `action_restore_defaults()`,
  and its `CommandResultScreen` subclass (`InspectResultScreen`,
  `FixMetadataResultScreen`, `MigrateResultScreen`, `ConfigResultScreen`)
- `tui/screens/metadata_screen.py` (User Story 8) — also:
  `_BaseConfirmScreen`, `MigrateConfirmScreen`, `FixMetadataConfirmScreen`;
  `FixMetadataScreen`/`MigrateScreen`'s `action_run()` pushes these
  instead of executing
- `tui/diff.py` (User Story 8) — `build_side_by_side_diff(before, after)`
  (replaced the old `diff_lines`/`render_diff`)
- `commands/fix_metadata.py` (User Story 8) — `compute_default_prompt_values()`,
  `PromptDefaults`, `parse_tuple_input()` (made non-private), all reused
  by both the CLI's own prompts and `FixMetadataConfirmScreen`
- `tui/status.py` — `StatusPanel`, reused unchanged (no new methods needed)

## Who verifies this contract

New/updated tests in `tests/integration/`: a static test asserting every
per-command screen's rendered field order/frame membership matches the
required/optional table above, including each frame's border style/color;
a dynamic test asserting the required frame's `border_subtitle` starts at
the correct initial count, updates on each required-field edit, and reads
`"0 remaining"` once all are filled; a menu-entry test asserting
`Option.prompt` line count and content; a Browse round-trip test using
`ModalScreen` push/dismiss; an add-on state-machine test exercising
type/backspace sequences for all 4 color groups; a static test asserting
every prep screen's identity frame shows the correct name/description; a
dynamic test asserting `app.screen` becomes the correct `CommandResultScreen`
subclass *immediately* on Run (before the worker resolves) showing the
identity frame and a pending progress indicator, that it flips to the
correct success/failure indicator and command-specific content once the
worker resolves, that a blocked Run (missing required field) never
navigates, that a second Run press while pending re-navigates to the same
instance rather than constructing a new one, and that "Back to form"
returns to the prep screen with fields unchanged from either state; a
dynamic test asserting Restore Defaults replaces the prep screen with a
fresh instance (`app.screen is not` the pre-reload screen) whose fields
show their opening values (including non-empty defaults) and whose
specialized-screen content (diff/current-config views) is likewise reset,
and that it's a no-op while fields are disabled.
