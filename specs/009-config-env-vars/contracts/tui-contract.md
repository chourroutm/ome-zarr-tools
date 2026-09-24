# TUI Contract: Menu Warning + Config Screen Rewrite

## `CommandMenuScreen` (the main menu, `tui/app.py`)

- Below the existing `OptionList` of commands, a warning row (a `Label`/`Static`, hidden by default — no height/space taken when there's nothing to warn about) appears when the active env-file (whatever `--env-file` value, if any, launched this TUI session — including via `ome-zarr-tools --env-file X interactive --tui`) contains one or more unrecognized `OME_ZARR_TOOLS_*` keys (FR-016).
- The row's text names every unrecognized key found (not just a count), so the user can act on it without leaving the menu.
- No env-file given at all → the row is absent entirely (not present-but-empty), matching every other optional-content pattern already used in this TUI (e.g. `build_field_frames`'s "a group with no fields produces no frame").

**Test** (`tests/integration/test_tui_screens.py` or a new `test_tui_menu.py`, headless Textual): launch `InteractiveTUIApp` with a mapping that includes one unrecognized key; assert the warning row is present and names it. Launch with no env-file / a clean one; assert the row is absent.

## `ConfigScreen` (`tui/screens/config_screen.py`) — full rewrite

Removed:
- The `--user`/`--project` scope `Select` and the conditional "Project directory" `Input` (`_scope_select`, `_project_dir_label`, `_project_dir_input`, `_refresh_scope_visibility`).
- The JSON `TextArea` editor and `json.loads`/`json.dumps` round-tripping in `action_run`/`_load_current`.
- `DefaultEntryButton`'s JSON-line rendering (`"key": value,`) and `_locate_existing_key`/`_location_from_offset`/`_new_key_insertion`'s JSON-syntax-aware insertion logic.

Added, replacing each:
- A required `PathField` (matching the pattern already used for `apply_mask`'s `--volume`/`--mask`, `from_images`' `--output_zarr`, etc.) bound to the `ENV_FILE` argument — file-only (`only="file"`), no default value, `count_empty_required`-tracked like any other required field so the frame's "N remaining" subtitle and Run-button gating work unchanged.
- A plain-text `TextArea` (no `language=`) showing the file's raw `KEY=VALUE` lines — `_load_current` calls `read_env_file(path)` (tolerating a not-yet-existing file as empty, matching `config set`'s own "creates if missing" semantics for a screen that hasn't saved yet) and renders it back as `KEY=VALUE\n`-joined text; `action_run` parses the edited text the same way `read_env_file` would (reusing that same parser, not a second implementation) and calls `write_env_file`.
- `DefaultEntryButton` inserts a plain `KEY=VALUE` line instead of a JSON entry, using the corrected, registry-driven variable names (`build_defaults_entries` now sourced from `CONFIGURABLE_VARIABLES` + each target's `click.Option.default`, not the old buggy `collect_default_values()` — this is exactly the fix for the `output_format` collision, applied to the TUI's own reference view too, per spec.md FR-010).
- Unrecognized-key detection: after loading/before saving, if the current text contains an unrecognized `OME_ZARR_TOOLS_*` key, `action_run` shows it as a blocking `self.notify(..., severity="error")` (matching `config` subcommands' error-level severity, since this screen's Save is the TUI equivalent of running `config set`) rather than a passive warning — consistent with FR-016's "config subcommand ... error-level" bucket, since this screen directly maps to `config set`.
- `_invocation_text()` now returns `ome-zarr-tools config set <path> <KEY=VALUE ...>` using the `PathField`'s current value, matching the new positional CLI shape.
- `ConfigResultScreen` shows the plain-text file content instead of a JSON `TextArea` (still read-only).

**Tests** (`tests/integration/test_tui_screens.py`, existing `_ConfigApp`/`test_config_screen_*` tests rewritten):
- Golden path: fill the `ENV_FILE` field, click a default-entry button, confirm it inserts a `KEY=VALUE` line (not JSON), Run, confirm `ConfigResultScreen` shows the plain-text content and the file on disk matches.
- Edge case: an unrecognized `OME_ZARR_TOOLS_*` key in the editor blocks Run with an error notification, editor content preserved (mirrors the JSON-invalid-blocks-save behavior this screen already had, per its own docstring reference to "Save validates ... (blocking, edit preserved)").
