"""Spec 004 US1: the command menu's logo (three OME-colored squares)."""

from __future__ import annotations

from textual.app import App, ComposeResult

from ome_zarr_tools.tui.logo import (
    LOGO_MIN_HEIGHT,
    LOGO_MIN_WIDTH,
    OME_BLUE,
    OME_GREEN,
    OME_RED,
    Logo,
    render_logo,
)


class _LogoApp(App):
    def compose(self) -> ComposeResult:
        yield Logo()


def test_render_logo_uses_all_three_ome_colors_in_order():
    text = render_logo()
    assert "█" in text.plain
    colors_in_order = [span.style for span in text.spans if span.style]
    # De-duplicate consecutive/repeated spans while preserving first-seen order.
    seen_order = list(dict.fromkeys(colors_in_order))
    assert seen_order == [f"bold {OME_RED}", f"bold {OME_GREEN}", f"bold {OME_BLUE}"]


async def test_set_visible_for_size_shows_logo_at_normal_terminal_size():
    app = _LogoApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        logo = app.query_one(Logo)
        logo.set_visible_for_size(80, 30)
        assert logo.display is True


async def test_set_visible_for_size_hides_logo_below_minimum_size():
    app = _LogoApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        logo = app.query_one(Logo)
        logo.set_visible_for_size(LOGO_MIN_WIDTH - 1, LOGO_MIN_HEIGHT - 1)
        assert logo.display is False
