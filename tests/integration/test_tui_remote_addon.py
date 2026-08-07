"""Spec 004 US5: colored remote-scheme add-on for path fields."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.color import Color
from textual.widgets import Button

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen
from ome_zarr_tools.tui.fields import PathField

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


class _ScreenApp(App):
    def __init__(self, screen_factory) -> None:  # noqa: ANN001
        super().__init__()
        self._screen_factory = screen_factory

    def on_mount(self) -> None:
        self.push_screen(self._screen_factory())


def _stack_dir_field(screen) -> PathField:  # noqa: ANN001
    return next(
        s.widget
        for s in screen._field_specs
        if isinstance(s.widget, PathField) and s.widget.input.id == "field-stack_dir"
    )


@pytest.mark.parametrize(
    ("scheme", "remainder", "color"),
    [
        ("gs://", "bucket/key", "blue"),
        ("gcs://", "bucket/key", "blue"),
        ("s3://", "bucket/key", "orange"),
        ("az://", "container/key", "cyan"),
        ("abfs://", "container/key", "cyan"),
        ("http://", "example.com/data.zarr", "gray"),
        ("https://", "example.com/data.zarr", "gray"),
    ],
)
async def test_addon_shown_with_correct_color_per_scheme(scheme, remainder, color):
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        field = _stack_dir_field(app.screen)
        field.input.focus()
        await pilot.press(*(scheme + remainder))
        await pilot.pause()

        assert field._addon_label.display is True
        assert str(field._addon_label.content) == scheme
        assert field._addon_label.styles.color.hex == Color.parse(color).hex
        assert field.input.value == remainder
        assert field.value == scheme + remainder


async def test_bare_scheme_alone_stays_plain_editable_text():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        field = _stack_dir_field(app.screen)
        field.input.focus()
        await pilot.press(*"gs://")
        await pilot.pause()

        assert field._addon_label.display is False
        assert field.input.value == "gs://"
        assert field.value == "gs://"


async def test_backspace_to_empty_reverts_addon_to_plain_editable_scheme():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        field = _stack_dir_field(app.screen)
        field.input.focus()
        await pilot.press(*"gs://bucket")
        await pilot.pause()
        assert field._addon_label.display is True

        for _ in range(len("bucket")):
            await pilot.press("backspace")
        await pilot.pause()

        assert field._addon_label.display is False
        assert field.input.value == "gs://"

        # continuing to delete removes the scheme itself, character by character
        await pilot.press("backspace")
        await pilot.pause()
        assert field.input.value == "gs:/"


async def test_paste_full_url_in_one_action_triggers_addon_immediately():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        field = _stack_dir_field(app.screen)
        field.input.value = "s3://my-bucket/key"
        await pilot.pause()
        assert field._addon_label.display is True
        assert field.input.value == "my-bucket/key"


async def test_autocomplete_disabled_while_addon_shown_reenabled_after():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        field = _stack_dir_field(app.screen)
        assert field.autocomplete is not None
        assert field.autocomplete.suppressed is False

        field.input.focus()
        await pilot.press(*"gs://bucket")
        await pilot.pause()
        assert field.autocomplete.suppressed is True
        assert field.autocomplete.display is False

        for _ in range(len("bucket")):
            await pilot.press("backspace")
        await pilot.pause()
        assert field.autocomplete.suppressed is True  # bare scheme: still remote-recognized

        for _ in range(len("gs://")):
            await pilot.press("backspace")
        await pilot.pause()
        assert field.autocomplete.suppressed is False


async def test_browse_button_hidden_while_addon_shown_reappears_when_removed():
    """Browsing the local filesystem doesn't apply to a remote path, so the Browse
    button hides for as long as the add-on is shown (FR-019)."""
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        field = _stack_dir_field(app.screen)
        button = field.query_one(Button)
        children_before = list(field.children)
        assert children_before.index(button) == len(children_before) - 1
        assert button.display is True

        field.input.focus()
        await pilot.press(*"gs://bucket/key")
        await pilot.pause()
        children_after = list(field.children)
        assert children_after.index(button) == len(children_after) - 1  # position unchanged
        assert field._addon_label.display is True
        assert button.display is False

        for _ in range(len("bucket/key")):
            await pilot.press("backspace")
        await pilot.pause()
        assert field._addon_label.display is False
        assert button.display is True


async def test_cli_token_identical_between_addon_state_and_plain_text(monkeypatch, tmp_path):
    """FR-018/SC-008: the CLI token must be byte-for-byte identical to what a single
    plain-text field containing the same full value would produce -- checked directly
    against `widget_value_to_tokens`, which is the one function both paths go through."""
    from ome_zarr_tools.tui.fields import widget_value_to_tokens

    monkeypatch.chdir(tmp_path)
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        stack_dir_param = next(p for p in COMMANDS["from_images"].params if p.name == "stack_dir")
        field = _stack_dir_field(screen)

        field.input.focus()
        await pilot.press(*"gs://my-bucket/data")
        await pilot.pause()
        assert field._addon_label.display is True  # genuinely in add-on state
        tokens_addon_state = widget_value_to_tokens(stack_dir_param, field)

        assert tokens_addon_state == ["--stack_dir", "gs://my-bucket/data"]
        assert field.value == "gs://my-bucket/data"
