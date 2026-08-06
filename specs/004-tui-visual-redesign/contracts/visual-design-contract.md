# Contract: TUI Visual Design Tokens

The concrete, testable values behind spec.md's FRs — the single source of
truth tests and future screens check against, so the redesign doesn't drift
back into per-screen one-offs (the same reasoning as `003`'s
`shortcut-contract.md`).

## Command menu (User Story 1)

| Element | Rule |
|---|---|
| Logo | Static ASCII art, Matryoshka-doll motif, shown above the `OptionList`. Hidden (not clipped) below a minimum terminal size. |
| Menu entry | 3-line Rich `Option` prompt: line 1 = command name (bold), line 2 = `command.help`/`short_help` (blank if none), line 3 = blank spacer. |
| Header clock | `Header(show_clock=True)` on every screen. |

## Field group frames (User Story 2)

| Element | Rule |
|---|---|
| Order | Required frame before Optional frame. Empty group → that frame is omitted entirely. |
| Border | `border: round $panel;` (or the app's equivalent border-color variable) — one style, reused everywhere a frame appears. |
| Title | `border_title = "Required"` / `"Optional"`, exact strings, so tests can assert on them. |

## Field labels (User Story 3)

| Rule |
|---|
| `click.Parameter`-derived labels: `param.name.replace("_", " ").title()`. |
| Specialized-screen hand-built labels: already-human-readable literal text at the call site. |
| Required marker (trailing `*`) unchanged, appended after the label text. |
| CLI token generation (`widget_value_to_tokens`) is entirely independent of label text — never derived from it. |

## Browse picker (User Story 4)

| Element | Rule |
|---|---|
| Button | Every path-typed field: `Button("Browse", ...)`, `height: 3`, positioned to the right of the input (and, when present, to the right of the remote-path add-on). |
| Picker | `ModalScreen[Path \| None]`, rooted at the field's current value's parent dir (or cwd). |
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
| CLI token = add-on's scheme text (if shown) + `Input`'s text, always — identical to the same full string typed into a plain field. |

## Who implements this contract

- `tui/logo.py` — `Logo`, `LOGO`
- `tui/app.py` — `CommandMenuScreen` (menu entries, logo, header clock),
  `CommandFormScreen` (frames, labels, add-on, browse — via `fields.py`)
- `tui/fields.py` — `FieldSpec`, `build_field_frames`, `field_label`,
  `REMOTE_SCHEME_COLORS`, add-on `Horizontal` composition, Browse button
- `tui/screens/browse_screen.py` — `BrowsePickerScreen`, `SafeDirectoryTree`
- `tui/screens/inspect_screen.py`, `metadata_screen.py`, `config_screen.py`
  — each screen's own `FieldSpec` list + `build_field_frames()` call,
  human-readable labels, `Header(show_clock=True)`

## Who verifies this contract

New/updated tests in `tests/integration/`: a static test asserting every
per-command screen's rendered field order/frame membership matches the
required/optional table above; a menu-entry test asserting `Option.prompt`
line count and content; a Browse round-trip test using `ModalScreen`
push/dismiss; an add-on state-machine test exercising type/backspace
sequences for all 4 color groups.
