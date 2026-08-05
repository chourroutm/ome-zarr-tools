# Quickstart: Validate the Textual TUI for `interactive`

Prerequisites: this branch checked out, `pip install -e .[dev]` (or `uv pip install -e .[dev]`) run from the repo root — installs `textual`/`textual-autocomplete` alongside the existing runtime deps. No new dependencies were added during the `/speckit-clarify` redesign (research.md).

## 1. Automated test suite (covers all scenarios below, headlessly)

```bash
pytest tests/ -q
```
Expected: all tests pass, including `tests/contract/test_interactive_tui.py`, `tests/integration/test_interactive_tui.py`, `tests/integration/test_tui_execution.py`, `tests/integration/test_tui_diff.py`, and `tests/integration/test_tui_screens.py` — all driven via Textual's `App.run_test()`/`Pilot`, no real terminal needed. Validates FR-012.

## 2. User Story 1 — prompt-based flow is unchanged

```bash
ome-zarr-tools interactive
```
Expected: identical behavior to before this feature — numbered menu, one prompt at a time, `click.confirm`-based Run. (Covered by `001-rebuild-cli-commands`'s `tests/integration/test_interactive.py`; re-run here as a regression check.) Validates SC-001.

## 3. User Story 2 — full-screen mode, no button, manual check

```bash
ome-zarr-tools interactive --tui
```
In a real terminal: expect a full-screen command menu, no button anywhere. Select `apply_mask`. Confirm:
- Every field is visible and editable at once; the footer shows Run / Copy / Copy-and-exit shortcuts (exact keys per the footer's own labels).
- The equivalent command line is shown live, updating as fields change — no separate confirmation dialog ever appears.
- Editing an earlier field after moving to a later one works without restarting the form — validates SC-003.
- Pressing Copy copies the invocation (paste elsewhere to confirm, where the terminal supports OSC 52) and also adds it to the log; nothing runs. Validates SC-005.
- Pressing Escape from the form returns to the menu; a second Escape/Ctrl+C exits with nothing run.

## 4. User Story 3 — path autocomplete, manual check

Still inside `interactive --tui`, select `from_images` and focus `--stack_dir`. Type the start of a real directory name; expect a live-filtered suggestion list. Then focus `OUTPUT_ZARR` (doesn't exist yet) and type a made-up name — expect no suggestions, field still accepts input. Validates SC-002 and FR-008/FR-009/FR-013.

## 5. User Story 4 — fix_metadata/migrate diff, manual check

```bash
ome-zarr-tools from_images --stack_dir tests/fixtures/stack --voxel_size 1.0 --voxel_size 1.0 --voxel_size 2.0 /tmp/demo.zarr
ome-zarr-tools interactive --tui
```
Select `fix_metadata`, point it at `/tmp/demo.zarr`. Confirm a Diff View (before/after) and an editable JSON rich view both appear immediately, before Run is pressed — not only when something looks contentious. Edit a value to something invalid (e.g. a non-numeric voxel size) and confirm the error is flagged inline, blocking Run. Fix it, press Run, confirm it executes immediately (no extra confirmation) and the diff matches what was written. Repeat for `migrate` with `--target_version 0.5`: confirm the rich view is a read-only preview that updates if you change the target version, still before Run. Validates SC-006 and FR-018/FR-019.

## 6. User Story 5 — live status and log, manual check

Run `from_images` again from the TUI against a larger stack (or `apply_mask`). While it runs (Run already pressed):
- Confirm a status indicator is visible — a progress bar once the underlying dask work has a known size, or an animated sparkline before/if it doesn't.
- Press the log-toggle shortcut; confirm the log appears showing the same messages the plain CLI would print, and toggling again hides it without interrupting the run.
- Confirm the TUI stays open and responsive throughout (not frozen) and shows a clear success/failure result at the end. Validates FR-014/FR-015.

## 7. User Story 6 — inspect panels, manual check

Select `inspect` against `/tmp/demo.zarr`. Confirm a JSON panel (scrollable, syntax-highlighted, one block per level) and a structure-summary panel both exist, switchable via a keyboard shortcut, and that their content matches `ome-zarr-tools inspect /tmp/demo.zarr --format json` / the default text output respectively. Validates SC-007 and FR-016.

## 8. User Story 7 — config editor, manual check

Select `config`. Confirm a scope picker (user/project), a view of current values vs. built-in defaults for the selected scope, and a JSON editor. Edit the JSON to something syntactically invalid; confirm saving is blocked with the edit preserved. Fix it and save; confirm `ome-zarr-tools config show --project ...` (direct CLI) reflects the change. Validates SC-008 and FR-017.

## 9. No-terminal fallback

```bash
echo | ome-zarr-tools interactive --tui
```
Expected: non-zero exit, a clear one-line message explaining an interactive terminal is required, no garbled terminal output or traceback. Validates FR-010 and SC-004.

## 10. Regression: rest of the suite still passes

```bash
ome-zarr-tools --help   # still lists interactive among the 8 commands, unchanged
pytest tests/contract tests/integration -q
```
Expected: the full `001-rebuild-cli-commands` suite plus this feature's tests (pre- and post-clarify) all pass together — including after the small, behavior-preserving extractions in `fix_metadata.py`/`migrate.py` (research.md).
