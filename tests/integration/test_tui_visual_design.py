"""Spec 004 US2/US3/US6: field-group frames, human-readable labels, identity frame.

Menu entry Rich content (US1) already has its own tests (test_tui_logo.py,
test_tui_menu.py).
"""

from __future__ import annotations

import click
from textual.app import App
from textual.containers import Vertical
from textual.widgets import Input

from ome_zarr_tools.cli import cli
from ome_zarr_tools.tui.app import CommandFormScreen
from ome_zarr_tools.tui.fields import field_label

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


class _ScreenApp(App):
    def __init__(self, screen_factory) -> None:  # noqa: ANN001
        super().__init__()
        self._screen_factory = screen_factory

    def on_mount(self) -> None:
        self.push_screen(self._screen_factory())


async def test_build_field_frames_order_and_border_style():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        frames = screen.query(Vertical)
        required = next(f for f in frames if f.id == "required-frame")
        optional = next(f for f in frames if f.id == "optional-frame")
        assert required.border_title == "Required"
        assert optional.border_title == "Optional"
        assert required.styles.border_top[0] == "tall"
        assert required.styles.border_top[1].hex.lower() == "#ff0000"
        assert optional.styles.border_top[0] == "tall"
        assert optional.styles.border_top[1].hex.lower() == "#0000ff"
        # required frame comes before optional frame in document order
        all_widgets = list(screen.query(Vertical))
        assert all_widgets.index(required) < all_widgets.index(optional)


async def test_required_only_command_shows_only_required_frame():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["extract"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        has_required = any(s.required for s in screen._field_specs)
        has_optional = any(not s.required for s in screen._field_specs)
        frame_ids = ("required-frame", "optional-frame")
        frames = {f.id for f in screen.query(Vertical) if f.id in frame_ids}
        assert ("required-frame" in frames) == has_required
        assert ("optional-frame" in frames) == has_optional


async def test_required_frame_subtitle_starts_correct_and_updates_live():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        required_count = sum(1 for s in screen._field_specs if s.required)
        assert screen._required_frame.border_subtitle == f"{required_count} remaining"

        voxel = screen.query_one("#field-voxel_size", Input)
        voxel.focus()
        await pilot.press(*"1,1,1")
        await pilot.pause()
        assert screen._required_frame.border_subtitle == f"{required_count - 1} remaining"

        outzarr = screen.query_one("#field-output_zarr-pathfield")
        outzarr.input.focus()
        await pilot.press(*"out.zarr")
        await pilot.pause()
        assert screen._required_frame.border_subtitle == "0 remaining"


async def test_frame_grouping_does_not_change_cli_tokens(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["apply_mask"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        volume = screen.query_one("#field-volume-pathfield")
        volume.input.focus()
        await pilot.press(*"vol.zarr")
        mask = screen.query_one("#field-mask-pathfield")
        mask.input.focus()
        await pilot.press(*"mask.zarr")
        await pilot.pause()
        invocation = screen._invocation_text()
        assert "vol.zarr" in invocation
        assert "mask.zarr" in invocation
        assert invocation.startswith("ome-zarr-tools apply_mask")


def test_field_label_is_human_readable_for_every_param():
    for command in COMMANDS.values():
        for param in command.params:
            label = field_label(param)
            assert "--" not in label
            assert not label.startswith("-")
            assert "_" not in label
            assert label == label.title() or " " not in param.name


def test_field_label_long_name_wraps_not_truncates(tmp_path):
    # A synthetic long parameter name to exercise wrap behavior explicitly.
    long_param = click.Argument(["a_very_long_parameter_name_indeed"])
    label = field_label(long_param)
    assert label == "A Very Long Parameter Name Indeed"
    # No ellipsis/truncation marker anywhere in the label itself.
    assert "…" not in label
    assert not label.endswith("...")


async def test_required_marker_still_present_with_human_readable_label():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        required_spec = next(s for s in screen._field_specs if s.required)
        label_texts = [str(label.content) for label in screen._required_frame.query("Label")]
        assert required_spec.label + " *" in label_texts


async def test_copy_uses_raw_flag_unaffected_by_label_casing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["apply_mask"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        volume = screen.query_one("#field-volume-pathfield")
        volume.input.focus()
        await pilot.press(*"vol.zarr")
        await pilot.pause()
        invocation = screen._invocation_text()
        assert "vol.zarr" in invocation
        assert "Volume" not in invocation  # the human-readable label must never leak into tokens


async def test_every_prep_screen_shows_identity_frame_with_name_and_description():
    from ome_zarr_tools.tui.screens.config_screen import ConfigScreen
    from ome_zarr_tools.tui.screens.inspect_screen import InspectScreen
    from ome_zarr_tools.tui.screens.metadata_screen import FixMetadataScreen, MigrateScreen

    cases = [
        (CommandFormScreen, COMMANDS["from_images"]),
        (InspectScreen, COMMANDS["inspect"]),
        (FixMetadataScreen, COMMANDS["fix_metadata"]),
        (MigrateScreen, COMMANDS["migrate"]),
        (ConfigScreen, COMMANDS["config"]),
    ]
    for screen_cls, command in cases:
        app = _ScreenApp(lambda screen_cls=screen_cls, command=command: screen_cls(command))
        async with app.run_test() as pilot:
            await pilot.pause()
            frame = app.screen.query_one("#identity-frame", Vertical)
            assert frame.border_title == command.name
            expected_desc = command.get_short_help_str(limit=70)
            assert expected_desc  # sanity: these real commands do have help text
            texts = [str(w.content) for w in frame.query("Label")]
            assert expected_desc in texts


async def test_identity_frame_blank_description_for_command_with_no_help():
    from textual.screen import Screen

    from ome_zarr_tools.tui.fields import build_identity_frame

    no_help_command = click.Command(name="no_help", callback=lambda: None, help=None)

    class _Screen(Screen):
        def compose(self):
            yield build_identity_frame(no_help_command)

    app = _ScreenApp(_Screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        frame = app.screen.query_one("#identity-frame", Vertical)
        assert frame.border_title == "no_help"
        label = frame.query_one("Label")
        assert str(label.content) == ""


async def test_identity_frame_visually_distinct_from_field_group_frames():
    app = _ScreenApp(lambda: CommandFormScreen(COMMANDS["from_images"]))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        identity = screen.query_one("#identity-frame", Vertical)
        required = screen.query_one("#required-frame", Vertical)
        assert identity.styles.border_top[0] != required.styles.border_top[0] or (
            identity.styles.border_top[1].hex != required.styles.border_top[1].hex
        )
