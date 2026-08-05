# Phase 0 Research: Textual-Based TUI for Interactive Mode

## Framework choice

- **Decision**: Use `textual` (≥8.0) for the full-screen interface, exactly as the user named it.
  **Rationale**: Explicit, non-negotiable requirement — not an AI technology choice to weigh alternatives on.
  **Alternatives considered**: N/A — the framework was specified by name in the request.

- **Decision**: Verified in this environment (installed `textual==8.2.8`) rather than assumed from documentation. Confirmed: `App`, `Screen`, `Input`, `OptionList`, `Select`, `Checkbox`, `Header`/`Footer` all import and construct correctly; `App.run_test()` provides a headless async context manager yielding a `Pilot` that can focus widgets, send keystrokes (`pilot.press(...)`), and pause for redraws (`pilot.pause()`) — confirmed with a working end-to-end smoke test (menu + Input + attached autocomplete, driven headlessly, asserted on final widget state).
  **Rationale**: Earlier features in this project (`001-rebuild-cli-commands`) were burned by trusting doc-summary assumptions about third-party APIs (`bioio_ome_zarr.OmeZarrWriter` vs. the real `OMEZarrWriter`, etc.) — verifying against the installed package up front avoids repeating that during `/speckit-implement`.
  **Alternatives considered**: Trusting published docs without a local check — rejected given the prior-feature experience above.

## Path autocomplete

- **Decision**: Use `textual-autocomplete`'s `PathAutoComplete` widget (`textual_autocomplete.PathAutoComplete(target=input_widget, path=".")`), attached to each path-type field's `Input`, rather than writing custom glob-matching/dropdown logic.
  **Rationale**: `PathAutoComplete` is purpose-built for exactly this — verified installable (`textual-autocomplete==4.0.6`) and working headlessly (typing into an `Input` with a mounted `PathAutoComplete` produced live-filtered results in the smoke test). It already handles debouncing/caching (`cache_size` constructor parameter) and tolerates a partial path matching nothing (the `Input` simply keeps whatever the user typed — satisfies FR-007 with no extra code). This directly satisfies FR-006 and FR-011 (inline, type-ahead, within the field) with far less code and risk than a hand-rolled implementation.
  **Alternatives considered**: Hand-rolled `os.scandir`-based suggestion list rendered in a custom dropdown — rejected as reinventing a well-tested widget for no benefit; would also need its own debounce/cache/keyboard-navigation logic that `PathAutoComplete` already provides.

- **Decision**: Each path field's `PathAutoComplete` starts rooted at `"."` (the current working directory) by default; if the field already has a non-empty value when the form opens (e.g. a remembered/default path), root suggestions at that value's parent directory instead.
  **Rationale**: Matches ordinary shell-completion expectations (complete relative to what's already typed) without needing per-field configuration.
  **Alternatives considered**: Always rooting at cwd regardless of existing value — rejected as less helpful when editing an existing path.

## Discovered during `/speckit-implement`: `PathAutoComplete` crashes on unreadable directory entries

- **Finding**: `PathAutoComplete.get_candidates()` wraps `os.scandir(directory)` in `try/except OSError`, but the per-entry `entry.is_dir()` call in the results loop right after it is **not** wrapped. On this shared, multi-user host, typing a real absolute path under `/tmp` (which contains other users' socket files and other entries this process can't stat) raised an uncaught `PermissionError` that crashed the whole Textual app — reproduced directly, not just in a test. This is a real bug users of `--tui` could hit in practice, not a test-environment artifact.
  **Decision**: Added `SafePathAutoComplete(PathAutoComplete)` in `tui/fields.py`, overriding `get_candidates` to catch `OSError` around the call to `super().get_candidates()` and return no suggestions for that keystroke rather than crashing. `build_autocomplete` uses this subclass instead of the raw `PathAutoComplete`.
  **Rationale**: Cheapest safe fix without forking/patching the third-party package; consistent with FR-007's existing requirement that a field with no matches must not block the user — treating "can't list this directory" the same as "nothing matched" is a reasonable degradation. A locked-in regression test (`tests/integration/test_interactive_tui.py::test_path_autocomplete_tolerates_no_match_and_unreadable_siblings`) exercises this against the real `/tmp`.
  **Alternatives considered**: Patching only the specific `entry.is_dir()` call (duplicating the rest of the method body) — rejected as more code more tightly coupled to the library's private implementation, for a fix that's no more correct in practice (either way, that directory's suggestions are unavailable for that keystroke). Reporting upstream and waiting — out of scope for this feature; worth doing separately.

## Widget mapping (click.Parameter → Textual widget)

Mirrors `interactive.py`'s existing `_prompt_tokens` branching (one rule per parameter kind), so the TUI's form-building logic and the prompt-based wizard's question-asking logic stay conceptually parallel and easy to keep in sync:

| Parameter kind | Prompt-based behavior (existing) | TUI widget |
|---|---|---|
| `click.Argument` | Always prompted, no default | `Input`, marked required; `PathAutoComplete` attached if the argument is `click.Path` |
| `Option`, `is_flag=True` | `click.confirm` | `Checkbox` |
| `Option`, `type=click.Choice` | N/A today (no Choice options exist in current commands except `inspect --format`) | `Select`, options = the Choice's allowed values |
| `Option`, `type=click.Path` | `click.prompt` | `Input` + `PathAutoComplete` |
| `Option`, `multiple=True` or `nargs>1` | Looped/space-separated raw entry | Single `Input`, same space-separated convention, with helper text explaining the format (kept as free text for v1 rather than a dynamic repeatable-field widget — smaller surface to build and test, and consistent with what the prompt-based flow already asks users to type) |
| `Option`, everything else | `click.prompt` with default shown | `Input`, pre-filled with the default |

**Decision**: Keep the `multiple`/`nargs>1` case as a single free-text `Input` (space-separated) rather than building a dedicated repeatable-field widget.
**Rationale**: Every such option today (`from_images --voxel_size`, `extract --corner`/`--size`/`--center`) is small (1–3 numbers); a dynamic add/remove-row widget would be more code and more to test for no real usability gain at this scale.
**Alternatives considered**: A repeatable sub-form (add/remove rows) — deferred; can be revisited if a future command needs a long repeatable list.

## Shared confirm-and-run step (prompt-based flow only, as of the `/speckit-clarify` redesign)

- **Decision**: `interactive.py`'s existing `_run_wizard` → `_confirm_and_run(command, tokens)` extraction (build invocation string, `click.confirm`, `command.main(...)`) stays exactly as built, and continues to be used **only by the prompt-based flow** (FR-001, unchanged). It is no longer called by the TUI path.
  **Rationale**: FR-005 was revised during `/speckit-clarify`: the TUI no longer shows a confirmation dialog, and per FR-014/FR-015 it must show *live* status/log while the command runs — which requires the command to execute *while the Textual app is still open*, not after it exits. The pre-clarify design ("exit the TUI, then call `_confirm_and_run` back in the plain terminal") can no longer satisfy the spec; see "Running a command from inside the TUI" below for the replacement.
  **Alternatives considered**: N/A — this is a straightforward consequence of the revised FR-005/FR-014/FR-015, not a fresh design choice.

## Running a command from inside the TUI (worker thread + dask Callback + stdout capture)

The Textual app's event loop is asyncio-based and single-threaded; `command.main(args=tokens, standalone_mode=False)` is a synchronous, blocking call (it runs the real command function, e.g. `apply_mask`'s dask/zarr writes). Calling it directly on the event loop would freeze the entire UI — no status updates, no way to see the log, no way to react to a cancel — for the whole duration of the command. Verified in this environment:

- **Decision**: Run `command.main(...)` inside a Textual worker thread via `self.run_worker(self._execute, thread=True)`; push any UI updates it needs to make back to the main thread via `self.app.call_from_thread(callback, ...)`. Both APIs confirmed present and match this exact use case (`App.run_worker(work, thread=True)`, `App.call_from_thread(callback, *args, **kwargs)`).
  **Rationale**: This is Textual's documented pattern for blocking/synchronous work; it keeps the UI thread free to redraw the status indicator and handle keypresses (e.g. a future cancel action) while the real command runs unmodified.
  **Alternatives considered**: Making the underlying command functions themselves `async`/cooperative — rejected as a much larger, invasive change to `001`'s already-shipped, tested commands, for no benefit over a worker thread.

- **Decision**: For progress, register a `dask.callbacks.Callback` (context-manager form, scoped to the `command.main(...)` call) with `start_state` and `posttask` hooks. Verified directly: `len(dsk)` inside `start_state` gives the exact total task count for a dask graph, and `posttask` fires once per completed task — confirmed with a real `dask.array` computation (201 tasks reported at start, 201 `posttask` calls observed, matching exactly). On each `posttask`, call back to the UI thread to advance the `ProgressBar`.
  **Rationale**: This observes *any* dask computation the running command happens to perform — `from_images` (image read/rechunk/write), `extract` (crop compute), `apply_mask` (mask math/write), and `migrate` (via `ngff-zarr`, which itself uses dask for the array read/write) — **without any of those commands' code being modified or even aware the TUI exists.** This is what makes FR-014's "progress bar when quantifiable" achievable without a cross-cutting change to `001`.
  **Alternatives considered**: Adding an explicit progress-callback parameter to every command function in `001` — rejected as unnecessarily invasive to already-shipped, tested code, for a capability `dask`'s own callback system already provides generically. Parsing `click.echo` output for progress hints — rejected as fragile (coupling to exact message wording) compared to a structural task-count signal.

- **Decision**: For commands (or portions of a command's run) that produce no dask task graph at all — `config`, `inspect`, and the early/late parts of `fix_metadata`/`migrate` before/after their dask-backed work — no `start_state` event fires, so no total is ever known. The status indicator starts as the animated `Sparkline` (see below) and only switches to a `ProgressBar` if/when a `start_state` event actually arrives.
  **Rationale**: This is exactly the behavior spec.md's own Edge Cases already anticipated ("a command's work becomes countable only partway through... status indicator may switch from a sparkline to a progress bar at that point") — the dask-Callback signal maps onto that requirement directly, it isn't a new rule invented here.
  **Alternatives considered**: Treating dask-free commands as always instantaneous / skipping the status indicator entirely for them — rejected as inconsistent (FR-014 doesn't carve out exceptions), and the sparkline is cheap to show regardless of duration.

- **Decision**: For the log (FR-015), redirect `sys.stdout` during the worker-thread `command.main(...)` call to a small stream object whose `.write()` forwards each chunk to the UI thread (`call_from_thread`) to append to a `RichLog`. Every command already writes its user-facing messages via `click.echo`, which writes to `sys.stdout` by default — no command code changes needed.
  **Rationale**: Reuses exactly what already prints today; the log is a strict superset of what a user watching the plain-text CLI already sees, just captured into a toggleable panel instead of scrolling past in the terminal.
  **Alternatives considered**: Wrapping `click.echo` itself (monkeypatching) — rejected as more invasive/fragile than redirecting the standard stream `click.echo` already targets.

## Status indicator widgets: `ProgressBar` and `Sparkline`

- **Decision**: Use Textual's own built-in `ProgressBar` widget (`textual.widgets.ProgressBar`) for quantifiable progress, and Textual's own built-in `Sparkline` widget (`textual.widgets.Sparkline`) — fed a small rolling buffer of synthetic values updated on a timer (`set_interval`) while a command is running with no known total — for the indeterminate case. Both confirmed present in the installed `textual==8.2.8` and constructible as expected.
  **Rationale**: The user's own wording ("progress bar... or an animated sparkline") maps directly onto two widgets Textual already ships — no need to build either from scratch, and `Sparkline` in particular is a literal, exact match for the term used in the spec, not an approximation via a generic spinner.
  **Alternatives considered**: Textual's `LoadingIndicator` (a built-in spinner) for the indeterminate case — a reasonable alternative, but rejected in favor of `Sparkline` specifically because the spec's own wording names "sparkline," and an animated sparkline (small bars of "activity" rippling) reads as more informative than a bare spinner for a CLI tool whose commands are themselves data-shaped.

## Rich JSON views: `TextArea(language="json")`

- **Decision**: Use Textual's built-in `TextArea` widget with `language="json"` for every "rich view" surface in the spec: `inspect`'s per-level JSON panel (FR-016, read-only), `config`'s JSON editor (FR-017, editable), and `fix_metadata`'s directly-editable proposed-metadata view (FR-018). Verified: `TextArea().available_languages` includes `"json"` in the installed version, giving syntax highlighting for free.
  **Rationale**: One widget, already installed, covers every "rich JSON" requirement in the spec with built-in syntax highlighting and (for the editable cases) built-in text editing, scrolling, and cursor handling — no custom JSON-pretty-printing-with-color code needed.
  **Alternatives considered**: A custom `Tree` widget (also built into Textual) for a collapsible JSON tree view — more discoverable for deeply nested structures, but rejected for v1 as more code for a benefit (collapse/expand) the spec doesn't ask for; `TextArea` with `read_only=True` and pretty-printed JSON is sufficient for "scrollable JSON of each level" (FR-016) as written.

## Diff rendering: stdlib `difflib` + `RichLog`

- **Decision**: Compute diffs with the standard library's `difflib.unified_diff` over the pretty-printed JSON (old vs. proposed metadata, one line per JSON key/value via `json.dumps(..., indent=2)`), then render into a `RichLog` widget with `+`/`-` lines colored green/red via Rich `Text` styling.
  **Rationale**: No new dependency; `difflib` is exactly built for this, and `RichLog` (already used elsewhere in the Textual ecosystem, confirmed importable) accepts styled `rich.text.Text` objects directly.
  **Alternatives considered**: A dedicated third-party diff widget — none identified in the already-adopted dependency set (`textual`, `textual-autocomplete`); adding one for a feature `difflib` + `RichLog` already covers isn't justified.

## `fix_metadata`/`migrate` diff & rich-view previews (no restructuring of already-shipped commands)

This was the highest-risk open question from this planning pass: computing an accurate "before/after" preview for `fix_metadata` and `migrate` *before* Run is pressed, without either (a) actually writing to the dataset early, or (b) invasively restructuring the two already-shipped, tested `001` commands into multi-phase APIs the generic TUI-execution model (tokens → `command.main()`) would have to special-case.

- **Decision (`fix_metadata`)**: Extract the pure "build proposed multiscales metadata from these field values" logic already inside `fix_metadata`'s command function into a standalone function (e.g. `build_proposed_multiscales(name, spatial_unit, voxel_size, axis_names, dataset_paths) -> list[dict]`), used by both the unchanged CLI command body and the TUI's diff/rich-view. The TUI computes the diff by reading the dataset's current metadata (already-existing `io.ome_metadata.read_multiscales`, no write) and calling this extracted function with whatever the form's fields currently hold — entirely in-memory, no dataset access beyond the read already needed to populate the form.
  **Rationale**: The "proposed metadata" for `fix_metadata` is, today, literally constructed from the same field values the form already collects (name/unit/voxel size/axes) — there is no hidden logic only the real command run can produce. Extracting a pure function (same pattern already proven low-risk with `interactive.py`'s `_confirm_and_run`) avoids duplicating that construction logic in two places (a real drift risk) without touching `fix_metadata`'s CLI behavior at all.
  **Alternatives considered**: Duplicating the proposed-metadata-building logic directly inside the TUI — rejected, exactly the kind of two-copies-that-can-drift risk pure-function extraction avoids.

- **Decision (`migrate`)**: Extract `migrate`'s version-detection logic (already a tiny, already-pure call to `io.ome_metadata.detect_version`) and add a small `preview_migration(path, target_version) -> attrs dict` helper that calls the *same* `ngff_zarr.from_ngff_zarr()`/`to_ngff_zarr()` pair the real command already uses, but writes the preview to a `zarr.storage.MemoryStore()` instead of `migrate`'s real temp-directory-then-swap path. Verified directly: `to_ngff_zarr(MemoryStore(), multiscales, version=target)` succeeds and the resulting group's `.attrs` are readable with no filesystem I/O and nothing to clean up.
  **Rationale**: `migrate`'s real conversion logic (0.4↔0.5 schema translation, axes/omero restructuring) lives inside `ngff-zarr`, not inside `migrate.py` itself — the preview needs to invoke that same real logic to be accurate, but doing so against an in-memory store is exactly as correct as the real disk-based conversion and costs nothing to discard. Run still invokes the unmodified, real `migrate` CLI command afterward (which repeats the conversion against the real path) — a small amount of duplicated work in exchange for zero changes to `migrate`'s tested, atomic temp-then-swap write behavior.
  **Alternatives considered**: Restructuring `migrate.py` into separate "prepare" (write to temp, return diff) and "finalize" (swap) phases the TUI could call across two user actions — rejected: this would require the generic TUI-execution model to special-case `migrate` specifically (breaking the "any click.Command, same tokens→`command.main()` path" design every other command relies on), and touches already-shipped, tested write/backup/swap logic for a benefit (avoiding one redundant in-memory conversion) that isn't worth the risk. Calling the *real* `migrate` command early (to a real temp path) for the preview and reusing that temp path on Run — rejected as more invasive than an in-memory preview and still needing its own cleanup-on-cancel handling.

## Discovered during `/speckit-implement`: `fix_metadata`/`migrate` can't actually run via `command.main()` from the TUI

The plan above assumed Run, for every command including `fix_metadata`/`migrate`, would invoke `command.main(args=tokens, standalone_mode=False)` the same generic way `CommandFormScreen` does. Building `metadata_screen.py` surfaced why that's wrong for these two specifically: **both commands have their own internal `click.confirm(...)` gate** (`fix_metadata`'s "Write this metadata...?" and `migrate`'s "Migrate ... ?"), and `fix_metadata` additionally collects its field values via `click.prompt(...)` calls, not CLI flags. Neither is answerable from a Textual worker thread with no real stdin attached — invoking either command via `command.main()` from Run would hang waiting for input that will never come.

- **Decision**: Extract each command's write tail into a plain function that takes already-known values and does the work with **no interactive prompting or confirmation**: `fix_metadata.write_metadata(path, group, proposed_multiscales) -> Path` (backup, write, validate, restore-on-failure) and `migrate.apply_migration(path, group, target_version) -> Path` (backup, real temp-then-swap convert, validate). `metadata_screen.py`'s Run action calls these directly — not through `command.main()` — wrapped in the same worker-thread mechanism as every other command (`tui/execution.py`, generalized to accept an arbitrary callable, not only "a click.Command plus tokens"). Each CLI command's own body is otherwise unchanged: it still prompts/confirms interactively and then calls its own newly-extracted tail function.
  **Rationale**: This is the direct consequence of FR-019 ("Run still executes on a single keypress... no separate modal confirmation") applied honestly: the TUI's Run for these two commands was always meant to skip their internal confirm step (that's the whole point of showing the diff/rich view first), so calling the tail function directly — deliberately bypassing the confirm/prompt wrapper — matches the requirement precisely, rather than fighting it by trying to make `command.main()` work non-interactively. It's the same pure-function-extraction pattern already used for `build_proposed_multiscales`/`preview_migration`, just extended one layer further (the write, not just the proposed-content computation).
  **Alternatives considered**: Adding new CLI flags (`--name`/`--unit`/`--voxel_size`/`--axes` for `fix_metadata`, a `--yes` flag for both) so `command.main()` *could* be driven non-interactively — rejected as a larger, less clean change to `001`'s CLI surface (new flags to document, test, and keep in sync) for no benefit over calling the already-needed extracted function directly; the TUI never needed `fix_metadata`'s CLI surface to grow, only its logic to be reachable as a function.

## Clipboard (Copy / Copy-and-exit, FR-006/FR-007)

- **Decision**: Use Textual's built-in `App.copy_to_clipboard(text)`, which writes an OSC 52 terminal escape sequence. Verified by reading its implementation: it is **fire-and-forget** — it always writes the escape sequence and returns `None`, with no way to detect whether the terminal actually applied it. Because there's no failure signal to branch on, Copy and Copy-and-exit MUST call `copy_to_clipboard()` **and** unconditionally also show the command line as a selectable line in the log panel — not "try, then fall back only on failure" (there is no detectable failure), but "always do the best-effort OS-clipboard write, and always also leave a guaranteed-working copy path visible."
  **Rationale**: This is the practical, honest interpretation of the user's own clarification answer ("try OS clipboard, fall back to in-app") given what the verified API can actually signal — strictly more helpful than the literal conditional-fallback reading, never less.
  **Alternatives considered**: Skipping the in-app fallback and trusting `copy_to_clipboard()` alone — rejected: the docstring itself notes it doesn't work on macOS Terminal, and OSC 52 forwarding is commonly disabled or unsupported over SSH, which matters directly for this project's HPC/remote-session usage pattern (already a real issue found during `/speckit-implement`'s `PathAutoComplete` work).

## No-interactive-terminal fallback (FR-010, unchanged)

- **Decision**: Before starting the Textual app, check `sys.stdin.isatty()` and `sys.stdout.isatty()`; if either is `False`, raise the existing `ome_zarr_tools.core.errors.CliError`.
  **Rationale**: Unchanged from the pre-clarify plan — still the simplest, most predictable check; reused rather than re-derived.
  **Alternatives considered**: (unchanged) Letting Textual itself fail and catching its exception — rejected as less predictable than a plain `isatty()` guard.

## No-interactive-terminal fallback (FR-008)

- **Decision**: Before starting the Textual app, check `sys.stdin.isatty()` and `sys.stdout.isatty()`; if either is `False`, raise the existing `ome_zarr_tools.core.errors.CliError` with a message naming the problem, exactly the same convention every other command already uses for expected failures.
  **Rationale**: Reuses infrastructure from `001-rebuild-cli-commands` instead of inventing new error-handling; satisfies FR-008's "clear message, must not crash" and SC-004's "100% of the time" requirement with a simple, standard check — no need to actually attempt and catch a Textual startup failure.
  **Alternatives considered**: Letting Textual itself fail and catching its exception — rejected as it depends on Textual's internal error behavior for a non-tty stdout, which is less predictable and slower to verify than a plain `isatty()` guard.

**Output**: All `NEEDS CLARIFICATION` items from the Technical Context are resolved above (there were none outstanding — both clarifications from `/speckit-specify` were already resolved with the user before planning began); no open unknowns remain.
