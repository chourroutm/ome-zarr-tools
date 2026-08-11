# Quickstart: Reliable Copy & Exit

## Prerequisites

- `uv sync` (or equivalent) so `ome-zarr-tools` and its test dependencies are installed.
- A sample OME-Zarr dataset for filling in a form (any existing test fixture works).

## Automated validation

```sh
pytest tests/integration/test_tui_copy_exit.py -q
pytest tests/integration/test_interactive.py -q
ruff check src tests && ruff format --check src tests && mypy src
```

Expected: all pass. See [contracts/copy-exit-contract.md](./contracts/copy-exit-contract.md)
for exactly what each test asserts.

## Manual walkthrough (real terminal — headless `Pilot` tests can't fully
prove terminal-restoration timing; this is the T053-style follow-up item)

1. Launch `ome-zarr-tools interactive --tui` in a real terminal — ideally one
   where OSC 52 clipboard support is known to be broken (e.g. inside tmux
   without `set -g set-clipboard on`, or macOS Terminal.app) so you can
   confirm the fallback is actually doing the job it exists for.
2. Open any command (e.g. `inspect`), fill in `ZARR_PATH`, press `F7`
   ("Copy & exit").
3. Confirm the app exits cleanly back to your shell prompt, and that the
   line `Copied invocation: ome-zarr-tools inspect <path> ...` is visible in
   your terminal, selectable with the terminal's normal mouse/keyboard text
   selection.
4. Repeat on a terminal where OSC 52 *does* work (e.g. iTerm2, kitty) —
   confirm the invocation both lands on the clipboard (paste it somewhere)
   *and* is printed — the printed line is not suppressed just because the
   clipboard attempt likely succeeded.
5. Confirm plain "Copy" (`F6`, no exit) still leaves the app running with no
   line printed to the terminal (nothing to print yet — the app hasn't
   exited), and that exiting afterward via `Cancel`/`Escape` at the menu
   prints nothing either.
