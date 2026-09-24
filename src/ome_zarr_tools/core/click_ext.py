from __future__ import annotations

import click


class TuiOption(click.Option):
    """A ``click.Option`` that also accepts TUI-only presentation hints.

    Pass extra ``tui_*`` keyword arguments to ``@click.option(..., cls=TuiOption,
    tui_max_occurrences=2)`` to declare command-specific knowledge the TUI's
    field builder (``tui/fields.py``) can use -- e.g. how many times a
    ``multiple=True`` option realistically repeats -- right next to the
    option it describes, instead of hardcoding it into generic TUI widget
    code. Click itself, and the CLI at runtime, never see these: they're
    popped in ``__init__`` before delegating to ``click.Option``.
    """

    def __init__(
        self, *args: object, tui_max_occurrences: int | None = None, **kwargs: object
    ) -> None:
        self.tui_max_occurrences = tui_max_occurrences
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
