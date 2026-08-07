"""Spec 004 US4: Browse button + directory-tree picker for path fields."""

from __future__ import annotations

from textual.app import App
from textual.widgets import Button, DirectoryTree, Input

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen
from ome_zarr_tools.tui.fields import PathField
from ome_zarr_tools.tui.screens.browse_screen import BrowsePickerScreen, SafeDirectoryTree

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


class _ScreenApp(App):
    def __init__(self, screen_factory) -> None:  # noqa: ANN001
        super().__init__()
        self._screen_factory = screen_factory

    def on_mount(self) -> None:
        self.push_screen(self._screen_factory())


async def test_every_path_field_shows_browse_button_right_of_input():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        path_fields = [s.widget for s in screen._field_specs if isinstance(s.widget, PathField)]
        assert path_fields
        for field in path_fields:
            button = field.query_one(Button)
            assert button.styles.height.value == 3
            children = list(field.children)
            assert children.index(button) > children.index(field.input)


async def test_browse_does_not_disable_existing_typing_and_autocomplete(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demo_stack").mkdir()
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        stack_field = next(
            s.widget
            for s in screen._field_specs
            if isinstance(s.widget, PathField) and s.widget.input.id == "field-stack_dir"
        )
        stack_field.input.focus()
        await pilot.press(*"demo_stack")
        await pilot.pause()
        assert stack_field.input.value == "demo_stack"
        assert stack_field.autocomplete is not None
        assert stack_field.autocomplete.display is True


async def test_browse_picker_select_fills_field_leaves_others_unchanged(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    subdir = tmp_path / "mydata"
    subdir.mkdir()

    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        other_field = screen.query_one("#field-voxel_size_unit", Input)
        original_other_value = other_field.value

        stack_field = next(
            s.widget
            for s in screen._field_specs
            if isinstance(s.widget, PathField) and s.widget.input.id == "field-stack_dir"
        )
        button = stack_field.query_one(Button)
        button.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(button)
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, BrowsePickerScreen)

        tree = app.screen.query_one(SafeDirectoryTree)
        node = next(n for n in tree.root.children if n.data and n.data.path == subdir)
        tree.select_node(node)
        app.screen.post_message(DirectoryTree.DirectorySelected(node, subdir))
        await pilot.pause()

        assert app.screen is screen
        assert stack_field.input.value == str(subdir)
        assert other_field.value == original_other_value


async def test_browse_picker_cancel_leaves_field_unchanged(tmp_path):
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        stack_field = next(
            s.widget
            for s in screen._field_specs
            if isinstance(s.widget, PathField) and s.widget.input.id == "field-stack_dir"
        )
        stack_field.input.value = "unchanged"
        button = stack_field.query_one(Button)
        button.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(button)
        await pilot.pause()
        assert isinstance(app.screen, BrowsePickerScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert app.screen is screen
        assert stack_field.input.value == "unchanged"


async def _open_picker_rooted_below(pilot, tmp_path):  # noqa: ANN001
    """Shared setup: opens the browse picker rooted at ``tmp_path/parent_dir``
    (one level below ``tmp_path``, which holds an as-yet-unreachable sibling)."""
    parent_dir = tmp_path / "parent_dir"
    parent_dir.mkdir()
    child_dir = parent_dir / "child_dir"
    child_dir.mkdir()
    sibling = tmp_path / "sibling"
    sibling.mkdir()

    app = pilot.app
    screen = app.screen
    stack_field = next(
        s.widget
        for s in screen._field_specs
        if isinstance(s.widget, PathField) and s.widget.input.id == "field-stack_dir"
    )
    stack_field.input.value = str(child_dir)
    button = stack_field.query_one(Button)
    button.scroll_visible(animate=False)
    await pilot.pause()
    await pilot.click(button)
    await pilot.pause()
    picker = app.screen
    assert isinstance(picker, BrowsePickerScreen)
    assert picker.root == parent_dir  # rooted at the value's parent, per existing behavior
    return picker, parent_dir, sibling


async def test_browse_picker_path_input_prefilled_and_reroots_on_submit(tmp_path):
    """DirectoryTree only shows its root's descendants -- an editable path Input
    above the tree, pre-filled with the current root, lets the user type any path
    (including an ancestor/sibling of the initial root) and re-root by pressing
    Enter. This replaced an earlier Up-button/Backspace-only design that the user
    reported didn't work reliably in their real terminal."""
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        picker, parent_dir, sibling = await _open_picker_rooted_below(pilot, tmp_path)
        tree = picker.query_one(SafeDirectoryTree)
        assert tree.path == parent_dir
        assert not any(n.data and n.data.path == sibling for n in tree.root.children)

        path_input = picker.query_one("#root-path-input", Input)
        assert path_input.value == str(parent_dir)  # pre-filled with the current root

        path_input.value = str(tmp_path)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert picker.root == tmp_path
        assert tree.path == tmp_path
        assert any(n.data and n.data.path == sibling for n in tree.root.children)


async def test_browse_picker_path_input_rejects_non_directory(tmp_path):
    not_a_dir = tmp_path / "not_a_dir.txt"
    not_a_dir.write_text("x")

    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        picker, parent_dir, _sibling = await _open_picker_rooted_below(pilot, tmp_path)

        path_input = picker.query_one("#root-path-input", Input)
        path_input.value = str(not_a_dir)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert picker.root == parent_dir  # unchanged: not a valid directory
        assert picker.query_one(SafeDirectoryTree).path == parent_dir


def test_safe_directory_tree_filters_by_only_dir(tmp_path):
    (tmp_path / "a_dir").mkdir()
    (tmp_path / "a_file.txt").write_text("x")

    tree = SafeDirectoryTree(tmp_path, only="dir")
    filtered = list(tree.filter_paths([tmp_path / "a_dir", tmp_path / "a_file.txt"]))
    assert tmp_path / "a_dir" in filtered
    assert tmp_path / "a_file.txt" not in filtered


def test_safe_directory_tree_only_any_keeps_files_and_dirs(tmp_path):
    (tmp_path / "a_dir").mkdir()
    (tmp_path / "a_file.txt").write_text("x")

    tree = SafeDirectoryTree(tmp_path, only="any")
    filtered = list(tree.filter_paths([tmp_path / "a_dir", tmp_path / "a_file.txt"]))
    assert tmp_path / "a_dir" in filtered
    assert tmp_path / "a_file.txt" in filtered


def test_safe_directory_tree_tolerates_permission_denied_entry(tmp_path, monkeypatch):
    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()

    class _BoomPath(type(unreadable)):
        def is_dir(self, *a, **k):  # noqa: ANN001, ANN002, ANN003
            raise PermissionError("nope")

    boom = _BoomPath(unreadable)
    tree = SafeDirectoryTree(tmp_path, only="any")
    filtered = list(tree.filter_paths([boom]))
    assert filtered == []


async def test_browse_picker_roots_at_current_value_parent_directory(tmp_path):
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        stack_field = next(
            s.widget
            for s in screen._field_specs
            if isinstance(s.widget, PathField) and s.widget.input.id == "field-stack_dir"
        )
        stack_field.input.value = str(existing_dir / "sub_that_does_not_exist")
        button = stack_field.query_one(Button)
        button.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(button)
        await pilot.pause()
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, BrowsePickerScreen)
        assert picker.root == existing_dir
