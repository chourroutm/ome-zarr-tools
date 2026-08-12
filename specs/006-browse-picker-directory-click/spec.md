# Feature Specification: Browse picker directory-name click selects and closes

**Feature Branch**: `006-browse-picker-directory-click`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "In the TUI's Browse path picker (BrowsePickerScreen / SafeDirectoryTree), clicking directly on a directory's name/label in the tree (not the expand/collapse toggle icon) should select that directory and close the popup, filling the originating path field with the selected directory's path -- the same way it already works for path fields constrained to directories only (only="dir", e.g. fix_metadata/migrate/extract/inspect's ZARR_PATH). Currently this only works for "dir"-only fields; for fields that accept either a file or a directory (only="any", e.g. from_images' OUTPUT_ZARR argument, an output path that does not need to already exist), clicking a directory's name in the tree does not dismiss the popup -- it only expands/collapses the directory, requiring the user to fall back to typing the path manually in the root-path input instead."

## Clarifications

### Session 2026-08-12

- Q: Should this fix apply everywhere the Browse popup allows picking either a file or a directory, or only to `from_images`'s OUTPUT_ZARR field specifically? → A: Fix the shared Browse popup component, so every field with this mode benefits now and in the future -- confirmed to also include `extract`'s `--output` option, which has the identical gap today.
- Q: Should selecting an existing non-empty directory for an output-style field (like OUTPUT_ZARR) warn the user before filling the field, or fill it immediately with no warning? → A: No warning -- fill the field immediately, exactly like selecting an existing file already does today. Consistent with the existing file-selection path; the command itself still validates/confirms before writing anything.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pick an output folder by clicking its name (Priority: P1)

A user filling in `from_images`'s OUTPUT_ZARR field opens the Browse popup to choose where the converted dataset should go. They navigate the folder tree and, once they've found the right location, click directly on that folder's name to choose it -- the same natural interaction that already works for every other Browse popup in the app (picking an existing dataset to inspect, migrate, or fix). Today, that click does nothing but expand or collapse the folder; the only way to actually finish picking it is to fall back to typing the full path into the text box above the tree. This story makes the click itself do what it visibly looks like it should do.

**Why this priority**: This is the entire feature -- there is no smaller independently-valuable slice. It removes a dead-end interaction that is inconsistent with every other Browse popup the user has already learned to use elsewhere in the app.

**Independent Test**: Open `from_images`'s OUTPUT_ZARR Browse popup, click directly on a folder's name (not its expand/collapse icon) in the tree, and confirm the popup closes and the OUTPUT_ZARR field is filled with that folder's path.

**Acceptance Scenarios**:

1. **Given** the OUTPUT_ZARR Browse popup is open showing a folder tree, **When** the user clicks directly on a folder's name, **Then** the popup closes and OUTPUT_ZARR is filled with that folder's full path.
2. **Given** the same popup, **When** the user clicks the small expand/collapse icon next to a folder (not its name), **Then** the folder only expands or collapses -- the popup stays open and nothing is filled in.
3. **Given** any other Browse popup in the app that already only accepts an existing directory (e.g. `fix_metadata`, `migrate`, `extract`, `inspect`'s ZARR_PATH), **When** the user clicks a folder's name, **Then** behavior is unchanged from today -- the popup still closes and fills the field.
4. **Given** a Browse popup for a field that only accepts a file (not a directory), **When** the user clicks a folder's name, **Then** the folder only expands or collapses -- picking a folder is still not a valid choice for that field.
5. **Given** `extract`'s `--output` Browse popup (also a field accepting either a file or a directory), **When** the user clicks directly on a folder's name, **Then** the popup closes and `--output` is filled with that folder's path, exactly as it now does for OUTPUT_ZARR.

---

### Edge Cases

- What happens when the user clicks a folder's name for a folder that already contains files, on a field like OUTPUT_ZARR whose value doesn't need to already exist (i.e. the folder might already hold data that a subsequent conversion would write into)? The field is filled immediately, no warning shown (FR-006) -- consistent with selecting an existing file today.
- What happens when the user double-clicks a folder's name? The single click already selects and closes the popup, so there is nothing left for a second click to act on once the popup is gone.
- What happens if the user clicks a folder's name while the root-path text box above the tree has unsubmitted text in it? The click's selection takes effect immediately and closes the popup; the unsubmitted text in the box is discarded, matching how submitting an existing file has always behaved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Browse popup MUST select a directory and close itself, filling the originating field with that directory's full path, when the user clicks directly on the directory's name/label in the tree -- for every field that accepts either a file or a directory, not only fields restricted to directories.
- **FR-002**: This directory-name click MUST behave identically to clicking a file's name in the same popup (immediate selection and close), so the two feel like one consistent interaction rather than two different ones.
- **FR-003**: Clicking the tree's expand/collapse icon for a directory MUST continue to only expand or collapse it, in every Browse popup, regardless of what kind of field opened the popup -- this existing interaction is unaffected by this feature.
- **FR-004**: Browse popups for fields that only accept an existing directory MUST keep behaving exactly as they do today (directory-name click already selects and closes there).
- **FR-005**: Browse popups for fields that only accept a file MUST keep behaving exactly as they do today (a directory's name is not a valid choice there; clicking it only expands/collapses).
- **FR-006**: Selecting a directory that already contains files or subfolders, on a field whose value does not need to already exist, MUST fill the field immediately with no warning or confirmation prompt -- identical to how selecting an existing file already behaves today.

### Key Entities

- **Browse popup (path picker)**: The shared modal folder-tree used to fill in any path field in the TUI, regardless of which command's field opened it or what kind of path (file, directory, or either) that field accepts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In every Browse popup for a field that accepts either a file or a directory, clicking directly on a folder's name closes the popup and fills the field with that folder's path, 100% of the time -- with no need to also click the expand/collapse icon or fall back to typing the path by hand.
- **SC-002**: Every Browse popup's existing behavior -- directory-only fields, file-only fields, and the expand/collapse icon itself -- is unchanged, verified by re-running the app's existing picker interactions with no regressions.

## Assumptions

- Fix scope is confirmed in Clarifications above: the shared Browse popup behavior, not `from_images` specifically -- `extract`'s `--output` option shares the identical gap today and is fixed by the same change.
- No other Browse popup behavior changes: keyboard-driven selection (e.g. pressing Enter on a highlighted folder) and the root-path text box both already work today and are out of scope.
