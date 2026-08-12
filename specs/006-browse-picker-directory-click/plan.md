# Implementation Plan: Browse picker directory-name click selects and closes

**Branch**: `006-browse-picker-directory-click` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-browse-picker-directory-click/spec.md`

## Summary

Clicking a directory's name/label in the Browse popup's folder tree dismisses
the popup and fills the originating field today only for fields restricted to
directories (`only="dir"`). For fields that accept either a file or a
directory (`only="any"` — `from_images`'s OUTPUT_ZARR and `extract`'s
`--output`), the same click only expands/collapses the directory, silently
doing nothing useful — the user has to fall back to typing the path by hand.
The fix is a one-line change to `BrowsePickerScreen.on_directory_tree_directory_selected()`
in `tui/screens/browse_screen.py`: dismiss whenever `only != "file"`, mirroring
the symmetric guard the sibling `on_directory_tree_file_selected()` handler
already uses (`if self.only == "dir": return`). No new widgets, no new state,
no new dependencies.

## Technical Context

**Language/Version**: Python 3.10+ (existing project baseline)

**Primary Dependencies**: Textual (`DirectoryTree`/`ModalScreen`, already in use in the touched file) — no new dependencies

**Storage**: N/A

**Testing**: pytest + Textual's `App.run_test()`/`Pilot` (existing pattern used throughout `tests/integration/test_tui_browse_picker.py`)

**Target Platform**: Same as the rest of the TUI — any terminal Textual supports, exercised headlessly in CI via `run_test()`

**Project Type**: Single project (existing `src/ome_zarr_tools` CLI/TUI package)

**Performance Goals**: N/A — no measurable performance dimension to this change

**Constraints**: Must not change behavior for `only="dir"` or `only="file"` fields (spec FR-004/FR-005); must not change the expand/collapse icon's own click behavior (FR-003)

**Scale/Scope**: One method, one file (`tui/screens/browse_screen.py`); test additions in the existing `tests/integration/test_tui_browse_picker.py`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Code Quality & Best Practice**: The fix is a minimal edit to existing code (no new abstraction, no new module) — directly aligned with "prefer editing existing modules" and "no speculative configuration." PASS.
- **II. Test-First Development**: A failing regression test (directory-name click on an `only="any"` field does not currently dismiss) will be written before the fix, per the existing `test_tui_browse_picker.py` pattern. PASS (planned, see tasks.md).
- **III. Deliberate Commit Discipline**: No commit will be made without explicit request; tree must pass lint/type/test at each commit. PASS (process constraint, not a design one).

No violations. Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/006-browse-picker-directory-click/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/ome_zarr_tools/
├── tui/
│   └── screens/
│       └── browse_screen.py   # BrowsePickerScreen — the one file this feature changes
└── ...                        # rest of the existing package, unchanged

tests/
├── contract/
├── integration/
│   └── test_tui_browse_picker.py   # existing picker tests; new regression test(s) added here
└── unit/
```

**Structure Decision**: Existing single-project layout (`src/ome_zarr_tools/`, `tests/{contract,integration,unit}/`) is unchanged — this feature adds no new files to `src/`, only edits `tui/screens/browse_screen.py` and extends the existing `tests/integration/test_tui_browse_picker.py`.

## Complexity Tracking

*No constitution violations — section not applicable.*
