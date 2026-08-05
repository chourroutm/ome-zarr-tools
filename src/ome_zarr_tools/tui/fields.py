"""``click.Parameter`` -> Textual widget mapping for the Command Form screen.

Mirrors ``commands/interactive.py``'s ``_prompt_tokens`` branching (one rule per
parameter kind) so the TUI and the prompt-based wizard build the same CLI tokens
from equivalent answers -- see contracts/tui-contract.md § Widget mapping.
"""

from __future__ import annotations

from pathlib import Path

import click
from textual.widgets import Checkbox, Input, Select
from textual_autocomplete import DropdownItem, PathAutoComplete, TargetState


class SafePathAutoComplete(PathAutoComplete):
    """`PathAutoComplete` that tolerates unreadable directory entries.

    Upstream's `get_candidates` wraps `os.scandir()` in try/except OSError but not
    the per-entry `entry.is_dir()` call after it -- which can raise PermissionError
    for entries (e.g. another user's socket file) the process can't stat, crashing
    the whole app on a shared multi-user filesystem. Skip that directory's
    suggestions instead of crashing (FR-007: a field with no suggestions must not
    block the user).
    """

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        try:
            return super().get_candidates(target_state)
        except OSError:
            return []


def is_required(param: click.Parameter) -> bool:
    return isinstance(param, click.Argument) or bool(getattr(param, "required", False))


def is_path_param(param: click.Parameter) -> bool:
    return isinstance(param.type, click.Path)


def field_label(param: click.Parameter) -> str:
    if isinstance(param, click.Argument):
        return param.human_readable_name
    assert isinstance(param, click.Option)
    return param.opts[0]


def build_field_widget(param: click.Parameter) -> Checkbox | Select | Input:
    """Return the Textual widget for one ``click.Parameter``, per the widget mapping table."""
    field_id = f"field-{param.name}"

    if isinstance(param, click.Argument):
        return Input(placeholder=param.human_readable_name, id=field_id)

    assert isinstance(param, click.Option)

    if param.is_flag:
        return Checkbox(param.opts[0], value=bool(param.default), id=field_id)

    if isinstance(param.type, click.Choice):
        options = [(choice, choice) for choice in param.type.choices]
        default = param.default if param.default in param.type.choices else None
        return Select(options, value=default, id=field_id, allow_blank=default is None)

    default = None if param.required else param.default
    if default in (None, ()):
        default_str = ""
    elif isinstance(default, (list, tuple)):
        default_str = " ".join(str(d) for d in default)
    else:
        default_str = str(default)
    return Input(value=default_str, placeholder=param.opts[0], id=field_id)


def build_autocomplete(
    param: click.Parameter, widget: Checkbox | Select | Input
) -> SafePathAutoComplete | None:
    """Return a `PathAutoComplete` attached to `widget`, or None if `param` isn't a path field.

    Rooted at the field's current value's parent directory if non-empty, else "." (research.md).
    """
    if not is_path_param(param):
        return None
    assert isinstance(widget, Input)

    root = Path(widget.value).parent if widget.value else Path(".")
    if not root.is_dir():
        root = Path(".")
    return SafePathAutoComplete(widget, path=root, id=f"{widget.id}-autocomplete")


def widget_value_to_tokens(param: click.Parameter, widget: Checkbox | Select | Input) -> list[str]:
    """Convert one field widget's current value into the CLI tokens it represents."""
    if isinstance(param, click.Argument):
        assert isinstance(widget, Input)
        value = widget.value.strip()
        return [value] if value else []

    assert isinstance(param, click.Option)
    flag = param.opts[0]

    if param.is_flag:
        assert isinstance(widget, Checkbox)
        return [flag] if widget.value else []

    if isinstance(param.type, click.Choice):
        assert isinstance(widget, Select)
        select_value = widget.value
        if select_value is Select.BLANK or select_value in (None, ""):
            return []
        return [flag, str(select_value)]

    assert isinstance(widget, Input)
    raw = widget.value.strip()
    if not raw:
        return []
    parts = raw.split()

    if param.multiple:
        nargs = param.nargs or 1
        tokens: list[str] = []
        for i in range(0, len(parts), nargs):
            tokens.append(flag)
            tokens.extend(parts[i : i + nargs])
        return tokens

    if param.nargs and param.nargs > 1:
        return [flag, *parts]

    return [flag, raw]
