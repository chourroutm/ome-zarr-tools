from pathlib import Path

from textual.widgets import Input, OptionList

from ome_zarr_tools.cli import cli
from ome_zarr_tools.commands.interactive import _prompt_tokens
from ome_zarr_tools.tui.app import InteractiveTUIApp

COMMANDS = {name: cmd for name, cmd in cli.commands.items() if name != "interactive"}


def _menu_index(name: str) -> int:
    return sorted(COMMANDS).index(name)


async def _wait_for(pilot, predicate, attempts: int = 50) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause()


async def test_select_edit_revisit_and_run_executes(
    monkeypatch, tmp_path: Path, sample_ome_zarr, sample_mask_zarr
):
    """SC-003: editing an earlier field after moving on works, without restarting the form.

    Also covers FR-005: pressing Run (F5) executes immediately, no confirmation
    dialog -- the invocation was already visible in the form.
    """
    monkeypatch.chdir(tmp_path)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("apply_mask")
        await pilot.press("enter")
        await pilot.pause()

        volume_field = app.screen.query_one("#field-volume", Input)
        volume_field.focus()
        await pilot.press(*"first-attempt.zarr")
        await pilot.pause()
        assert volume_field.value == "first-attempt.zarr"
        assert "first-attempt.zarr" in app.screen._invocation_text()

        # Move on to the next field, then come back and revise the first one --
        # this is exactly what the strictly-sequential prompt-based flow can't do.
        mask_field = app.screen.query_one("#field-mask", Input)
        mask_field.focus()
        await pilot.press(*str(sample_mask_zarr))
        await pilot.pause()

        volume_field.focus()
        await pilot.pause()
        for _ in range(len("first-attempt.zarr")):
            await pilot.press("backspace")
        await pilot.press(*str(sample_ome_zarr))
        await pilot.pause()
        assert volume_field.value == str(sample_ome_zarr)
        assert str(sample_ome_zarr) in app.screen._invocation_text()

        form_screen = app.screen
        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(form_screen._log_lines))

    assert any("succeeded" in line for line in form_screen._log_lines)


async def test_cancel_from_form_returns_to_menu_not_full_exit():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("config")
        await pilot.press("enter")
        await pilot.pause()
        assert len(app.screen_stack) == 3  # default + menu + form

        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 2  # back to menu


async def test_cancel_from_menu_exits_with_no_side_effects():
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.return_value is None


async def test_required_field_blocks_run_until_filled(monkeypatch, tmp_path: Path, sample_ome_zarr):
    monkeypatch.chdir(tmp_path)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("inspect")
        await pilot.press("enter")
        await pilot.pause()

        form_screen = app.screen
        await pilot.press("f5")
        await pilot.pause()
        assert form_screen._log_lines == []  # required zarr_path still empty; Run was a no-op

        path_field = app.screen.query_one("#field-zarr_path", Input)
        path_field.focus()
        await pilot.press(*str(sample_ome_zarr))
        await pilot.press("f5")
        await _wait_for(pilot, lambda: bool(form_screen._log_lines))

    assert any("succeeded" in line for line in form_screen._log_lines)


async def test_copy_does_not_run_and_copy_and_exit_closes_the_app(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("config")
        await pilot.press("enter")
        await pilot.pause()

        form_screen = app.screen
        await pilot.press("f6")  # Copy
        await pilot.pause()
        assert app._clipboard == "ome-zarr-tools config set --user <key=value ...>"
        assert any("Copied" in line for line in form_screen._log_lines)
        assert form_screen._log_lines == [
            line
            for line in form_screen._log_lines
            if "succeeded" not in line and "failed" not in line
        ]  # nothing ran

        await pilot.press("f7")  # Copy & exit
        await pilot.pause()

    assert app.return_value is None


async def test_tui_tokens_match_prompt_wizard_for_equivalent_answers(monkeypatch, tmp_path: Path):
    """The TUI and the prompt-based wizard must build the same tokens for `apply_mask`."""
    import click

    import ome_zarr_tools.tui.app as tui_app_module

    monkeypatch.chdir(tmp_path)
    apply_mask = COMMANDS["apply_mask"]

    answers = iter(["vol.zarr", "mask.zarr", "0.5", "n"])
    monkeypatch.setattr(click, "prompt", lambda *a, **k: next(answers))
    monkeypatch.setattr(click, "confirm", lambda *a, **k: False)

    prompt_tokens: list[str] = []
    for param in apply_mask.params:
        prompt_tokens.extend(_prompt_tokens(param))

    captured: dict[str, list[str]] = {}

    def fake_run_command(app, command, tokens, on_done, **kwargs):
        captured["tokens"] = tokens

    monkeypatch.setattr(tui_app_module, "run_command", fake_run_command)

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("apply_mask")
        await pilot.press("enter")
        await pilot.pause()

        app.screen.query_one("#field-volume", Input).focus()
        await pilot.press(*"vol.zarr")
        app.screen.query_one("#field-mask", Input).focus()
        await pilot.press(*"mask.zarr")
        await pilot.pause()

        await pilot.press("f5")
        await pilot.pause()

    assert captured["tokens"] == prompt_tokens


async def test_path_autocomplete_suggests_real_matching_entries(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demo_stack").mkdir()
    (tmp_path / "other_dir").mkdir()

    from textual_autocomplete import PathAutoComplete

    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("from_images")
        await pilot.press("enter")
        await pilot.pause()

        stack_field = app.screen.query_one("#field-stack_dir", Input)
        autocomplete = app.screen.query_one("#field-stack_dir-autocomplete", PathAutoComplete)
        stack_field.focus()
        await pilot.press(*"demo")
        await pilot.pause()

        suggestions = [str(item.main) for item in autocomplete.option_list.options]
        assert any("demo_stack" in s for s in suggestions)
        assert not any("other_dir" in s for s in suggestions)


async def test_path_autocomplete_tolerates_no_match_and_unreadable_siblings(tmp_path: Path):
    """FR-009: no match found must not block continued typing.

    Also locks in the SafePathAutoComplete fix: typing a path under the real,
    shared /tmp (which contains other users' permission-denied entries on this
    host) must not crash the app -- see tui/fields.py's SafePathAutoComplete.
    """
    app = InteractiveTUIApp(COMMANDS)
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.screen.query_one(OptionList)
        ol.highlighted = _menu_index("from_images")
        await pilot.press("enter")
        await pilot.pause()

        stack_field = app.screen.query_one("#field-stack_dir", Input)
        stack_field.focus()

        # A real, shared, world-readable directory this process can't fully stat --
        # exercises the exact crash SafePathAutoComplete guards against.
        await pilot.press(*"/tmp/zzz_definitely_does_not_exist_anywhere")
        await pilot.pause()

        assert stack_field.value == "/tmp/zzz_definitely_does_not_exist_anywhere"
