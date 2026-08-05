# Phase 1 Data Model: Textual-Based TUI for Interactive Mode

All entities from `spec.md` § Key Entities are in-memory only, scoped to a single `interactive --tui` invocation — nothing here is persisted, except where a command's own Run action performs the same writes it always has (unchanged, real dataset/config writes, not part of this in-memory model).

## TUI Session

The Textual app's state for one run.

| Field | Type | Notes |
|---|---|---|
| `available_commands` | list of `click.Command` | Read from the parent `cli` group's `.commands`, excluding `interactive` itself — identical source to the prompt-based menu's `choices` (`interactive.py`), so the two UIs never drift out of sync (FR-003). |
| `selected_command` | `click.Command \| None` | Set when the user picks a command from the menu screen; `None` while on the menu. |
| `field_values` | `dict[str, str \| bool]` | Keyed by each of `selected_command.params`' `.name`; populated as the user edits the form. Flags are `bool`; everything else (including space-separated `multiple`/`nargs>1` entries) is the raw string the user typed. |
| `equivalent_invocation` | string | The live `ome-zarr-tools <command> [OPTIONS]` text, recomputed from `field_values` on every edit; always visible per FR-005. |
| `execution` | `CommandExecution \| None` | Present once Run has been pressed; `None` before that. See below. |
| `state` | enum (`"menu"`, `"form"`, `"running"`, `"cancelled"`, `"copied"`, `"done"`) | `"running"` covers the whole worker-thread execution window (status/log live); `"cancelled"` is reachable from `"menu"` or `"form"` only (Escape/Ctrl+C before Run — FR-005's no-side-effects guarantee); `"copied"` is a transient state after Copy/Copy-and-exit that doesn't imply anything ran. |

**Validation rules**:
- Transition to `"running"` is only reachable from `"form"` via the Run shortcut, and only once every `required` field is non-empty (an `Argument`, or a `required` `Option`) — mirrors the prompt-based flow's guarantee of never omitting a required value.
- `"cancelled"` is reachable from `"menu"` or `"form"` at any time and always skips execution entirely — once `"running"` has started, the command is no longer cancellable mid-flight (out of scope for this feature; see spec.md Assumptions).
- `equivalent_invocation` is recomputed via the same field-to-token conversion `interactive.py`'s `_prompt_tokens`/`widget_value_to_tokens` already use, so the text shown is identical in shape to what the prompt-based flow would build for the same answers.

## CommandExecution

The live state of one Run, from keypress to completion. Owned by `tui/execution.py`; read by `tui/status.py` to drive the widgets.

| Field | Type | Notes |
|---|---|---|
| `command` | `click.Command` | The command being executed. |
| `tokens` | `list[str]` | The CLI tokens Run was pressed with — identical to what `equivalent_invocation` displayed. |
| `status` | `StatusIndicator` | See below; starts as indeterminate, may become quantified mid-run. |
| `log` | `CommandLog` | See below. |
| `result` | enum (`"running"`, `"succeeded"`, `"failed"`) + optional error message | `"failed"` captures a `CliError`/exception from `command.main()`, surfaced in the log rather than crashing the TUI. |

**Validation rules**: `status`/`log` only ever receive updates via `App.call_from_thread` (never touched directly from the worker thread) — enforced by `tui/execution.py`'s design, not by a runtime check, per `research.md`'s verified `call_from_thread` usage.

## Status Indicator

| Field | Type | Notes |
|---|---|---|
| `mode` | enum (`"indeterminate"`, `"quantified"`) | Starts `"indeterminate"`; becomes `"quantified"` the first time a dask `start_state` callback reports a total (research.md). Never reverts. |
| `done` | int | Count of completed dask tasks so far (0 while `"indeterminate"`). |
| `total` | `int \| None` | Total dask tasks for the current run; `None` while `"indeterminate"`. |
| `sparkline_buffer` | list of float | Rolling window of synthetic activity values, refreshed on a timer while `mode == "indeterminate"`, feeding the `Sparkline` widget (research.md). |

**Validation rules**: `done <= total` whenever `total` is not `None`; `mode` transitions `"indeterminate" → "quantified"` at most once per `CommandExecution` (a command's task graph, once observed, doesn't become "unknown" again mid-run).

## Command Log

| Field | Type | Notes |
|---|---|---|
| `lines` | list of string | Captured `stdout` chunks from the running command, appended live (research.md's stdout-redirect approach). |
| `visible` | bool | Defaults `False`; toggled by the log keyboard shortcut (FR-015) independent of whether a command is running. |

**Validation rules**: Toggling `visible` never clears or pauses `lines` capture — the log keeps recording whether or not it's currently shown (Edge Cases: toggling the log doesn't interrupt the running command).

## Diff View

Computed for every `fix_metadata`/`migrate` form, before Run is pressable (FR-018).

| Field | Type | Notes |
|---|---|---|
| `before` | dict (parsed JSON) or `None` | The dataset's current metadata (`io.ome_metadata.read_multiscales`); `None`/empty for a dataset with no prior metadata (spec.md User Story 4, Acceptance Scenario 3). |
| `after` | dict (parsed JSON) | For `fix_metadata`: built by the extracted `build_proposed_multiscales(...)` from the form's current field values (research.md). For `migrate`: built by `preview_migration(path, target_version)` against an in-memory `zarr.storage.MemoryStore` (research.md) — recomputed if `target_version` changes. |
| `diff_lines` | list of styled line | `difflib.unified_diff` over `json.dumps(before, indent=2)`/`json.dumps(after, indent=2)`, rendered into a `RichLog` with +/- lines colored (research.md). |

**Validation rules**: `after` is recomputed whenever the relevant form fields change (for `fix_metadata`, any of name/unit/voxel-size/axes; for `migrate`, `target_version`) — the diff is always current, never stale relative to the form.

## Rich View/Edit Surface

| Field | Type | Notes |
|---|---|---|
| `command` | enum (`"fix_metadata"`, `"migrate"`, `"config"`) | Which command's rich surface this is (`inspect` has its own panels, described separately below, not an edit surface). |
| `editable` | bool | `True` for `fix_metadata` and `config`; `False` for `migrate` (a formatted preview — see spec.md Assumptions) by default. |
| `text` | string | The pretty-printed JSON currently shown/edited in the `TextArea(language="json")` (research.md). |
| `validation_error` | string or `None` | Set when `text` fails to parse as JSON, or (for `fix_metadata`) fails the same semantic validation the CLI enforces, or (for `config`) fails `config set`'s own validation. Run/save is blocked while non-`None`. |

**Validation rules**: `validation_error` must be `None` before Run can execute for `fix_metadata`, or before a save can complete for `config` — matches FR-018's "flagged... before Run can be pressed" and the Edge Cases entry for invalid config JSON.

## Inspect Panels

Not an edit surface — `inspect` is read-only (FR-016).

| Field | Type | Notes |
|---|---|---|
| `levels` | list of `{path, json_text}` | One pretty-printed, syntax-highlighted JSON block per resolution level — the same content `inspect --format json` already produces per level (`001-rebuild-cli-commands`'s `build_report`), rendered into a `TextArea(language="json", read_only=True)`. |
| `summary_text` | string | The structure-summary panel's content — the same figures `inspect`'s default text output already reports (shapes, chunk/shard layout, sizes, totals), reused rather than reformatted from scratch. |
| `active_panel` | enum (`"json"`, `"summary"`) | Which panel currently has focus/is shown; switchable via keyboard shortcut (spec.md Assumptions: tabbed, not simultaneous side-by-side). |

## Config Editor

| Field | Type | Notes |
|---|---|---|
| `scope` | enum (`"user"`, `"project"`) | User-selectable, matching the CLI's `--user`/`--project` (FR-017, per the resolved clarification). |
| `current_values` | dict | The selected scope's effective config, read the same way `config show` already reads it. |
| `default_values` | dict | The tool's built-in option defaults, shown for comparison (spec.md Assumptions: not a third config-file tier). |
| `editor` | `Rich View/Edit Surface` (`command="config"`, `editable=True`) | The JSON editor for the selected scope's config file. |

**Validation rules**: Switching `scope` reloads `current_values`/`editor.text` from that scope's file (or empty/defaults if the file doesn't exist yet, matching `config show`'s existing "not found" handling) — no cross-scope data leaks into the wrong editor.

## Path Suggestion List

The set of filesystem entries offered for one path field at one moment. Unchanged from the pre-clarify design.

| Field | Type | Notes |
|---|---|---|
| `field_name` | string | Which form field this suggestion list belongs to. |
| `query` | string | What the user has typed so far in that field. |
| `matches` | list of filesystem entries | Directories and files under `query`'s parent directory whose name starts with/matches the typed fragment. |

**Note**: Realized entirely by `textual-autocomplete`'s `SafePathAutoComplete` widget (per `research.md`) — application code does not construct or cache this list itself.

**Validation rules**: An empty `matches` list (nothing on disk matches, or the directory couldn't be read) never blocks continued typing in the field (FR-009) — the widget's own behavior, hardened by `SafePathAutoComplete`.
