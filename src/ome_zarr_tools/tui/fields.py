"""``click.Parameter`` -> Textual widget mapping for command prep screens.

Mirrors ``commands/interactive.py``'s ``_prompt_tokens`` branching (one rule per
parameter kind) so the TUI and the prompt-based wizard build the same CLI tokens
from equivalent answers -- see contracts/tui-contract.md § Widget mapping.

Spec 004 additions: ``FieldSpec``/``build_field_frames()`` (required/optional
framing, US2), human-readable ``field_label()`` (US3), ``PathField`` (Browse
button + remote-scheme add-on, US4/US5), ``build_identity_frame()`` (US6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import click
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, Select
from textual_autocomplete import DropdownItem, PathAutoComplete, TargetState

from ome_zarr_tools.core.zarr_path import is_remote_path

REMOTE_SCHEME_COLORS: dict[str, str] = {
    "gs://": "blue",
    "gcs://": "blue",
    "s3://": "orange",
    "az://": "cyan",
    "abfs://": "cyan",
    "http://": "gray",
    "https://": "gray",
}


class SafePathAutoComplete(PathAutoComplete):
    """`PathAutoComplete` that tolerates unreadable directory entries.

    Upstream's `get_candidates` wraps `os.scandir()` in try/except OSError but not
    the per-entry `entry.is_dir()` call after it -- which can raise PermissionError
    for entries (e.g. another user's socket file) the process can't stat, crashing
    the whole app on a shared multi-user filesystem. Skip that directory's
    suggestions instead of crashing (FR-007: a field with no suggestions must not
    block the user).

    ``suppressed`` (spec 004 US5/FR-016) forces the dropdown hidden regardless of
    search results -- overriding ``should_show_dropdown()`` directly rather than
    toggling ``.display``/`.disabled`` externally, since the base class's own
    ``_handle_target_update()`` reactively toggles ``.display`` on every keystroke
    based on search results and would otherwise fight over the same property.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.suppressed = False

    def should_show_dropdown(self, search_string: str) -> bool:
        if self.suppressed:
            return False
        return super().should_show_dropdown(search_string)

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
    """Human-readable label (spec 004 FR-005): capitalized, space-separated words."""
    return param.name.replace("_", " ").title()


def _path_only(param: click.Parameter) -> Literal["dir", "file", "any"]:
    ptype = param.type
    assert isinstance(ptype, click.Path)
    if ptype.dir_okay and not ptype.file_okay:
        return "dir"
    if ptype.file_okay and not ptype.dir_okay:
        return "file"
    return "any"


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
    if param.multiple and not isinstance(default, tuple):
        # `multiple=True` options with no explicit `default=` resolve to an
        # internal Click "unset" sentinel here, not `()` -- the runtime value is
        # always a tuple (empty if unset), so treat any non-tuple as empty too.
        default = ()
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


class PathField(Horizontal):
    """A path-typed field: optional remote-scheme add-on + Input + Browse button.

    Reacts to its own ``Input``'s value: shows a colored, non-editable scheme
    add-on when the value starts with a recognized remote scheme followed by
    more text (US5, FR-014/FR-015); the add-on reverts to plain editable text
    when the remainder is emptied (FR-017). Local autocomplete is hidden
    whenever the value is remote-recognized, bare scheme included (FR-016).
    Browse (US4, FR-008/FR-009) always stays to the right of the whole group
    (FR-019).
    """

    DEFAULT_CSS = """
    PathField {
        height: auto;
    }
    PathField > .path-field-addon {
        width: auto;
        padding: 0 1;
        text-style: bold;
    }
    PathField > Input {
        width: 1fr;
    }
    PathField > Button {
        height: 3;
        width: auto;
    }
    """

    def __init__(
        self,
        input_widget: Input,
        *,
        autocomplete: SafePathAutoComplete | None = None,
        only: Literal["dir", "file", "any"] = "any",
        id: str | None = None,  # noqa: A002
    ) -> None:
        super().__init__(id=id)
        self.input = input_widget
        self.autocomplete = autocomplete
        self.only = only
        self._addon_scheme: str | None = None
        self._addon_label = Label("", classes="path-field-addon")
        self._addon_label.display = False
        self._browse_button = Button("Browse", classes="browse-button")

    def compose(self) -> ComposeResult:
        yield self._addon_label
        yield self.input
        yield self._browse_button

    def on_mount(self) -> None:
        self._sync_addon_state()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input is self.input:
            self._sync_addon_state()

    def _sync_addon_state(self) -> None:
        if self._addon_scheme is not None:
            if self.input.value == "":
                scheme = self._addon_scheme
                self._addon_scheme = None
                self._addon_label.display = False
                self.input.value = scheme
                self.input.cursor_position = len(scheme)
            return

        value = self.input.value
        for scheme, color in REMOTE_SCHEME_COLORS.items():
            if value.startswith(scheme):
                remainder = value[len(scheme) :]
                if remainder:
                    self._addon_scheme = scheme
                    self._addon_label.update(scheme)
                    self._addon_label.styles.color = color
                    self._addon_label.display = True
                    self.input.value = remainder
                    self.input.cursor_position = len(remainder)
                if self.autocomplete is not None:
                    self.autocomplete.suppressed = True
                    self.autocomplete.action_hide()
                return

        if self.autocomplete is not None:
            self.autocomplete.suppressed = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button is not self._browse_button:
            return
        event.stop()
        from ome_zarr_tools.tui.screens.browse_screen import BrowsePickerScreen

        current = self.value
        root = Path(current).parent if current and not is_remote_path(current) else Path(".")
        if not root.is_dir():
            root = Path(".")
        self.app.push_screen(BrowsePickerScreen(root, self.only), self._apply_browse_result)

    def _apply_browse_result(self, path: Path | None) -> None:
        if path is None:
            return
        self._addon_scheme = None
        self._addon_label.display = False
        self.input.value = str(path)
        self.input.cursor_position = len(str(path))

    @property
    def value(self) -> str:
        """Full value including any add-on scheme prefix (FR-018)."""
        if self._addon_scheme is not None:
            return self._addon_scheme + self.input.value
        return self.input.value


AnyFieldWidget = Checkbox | Select | Input | PathField | Vertical


def build_field_spec(param: click.Parameter) -> FieldSpec:
    """Build the complete `FieldSpec` for one `click.Parameter`, including Browse/add-on
    wrapping for path fields."""
    label = field_label(param)
    required = is_required(param)
    widget = build_field_widget(param)
    autocomplete = build_autocomplete(param, widget)

    if is_path_param(param):
        assert isinstance(widget, Input)
        path_field = PathField(
            widget, autocomplete=autocomplete, only=_path_only(param), id=f"{widget.id}-pathfield"
        )
        return FieldSpec(
            label=label, widget=path_field, required=required, autocomplete=autocomplete
        )

    return FieldSpec(label=label, widget=widget, required=required, autocomplete=autocomplete)


def widget_value_to_tokens(param: click.Parameter, widget: AnyFieldWidget) -> list[str]:
    """Convert one field widget's current value into the CLI tokens it represents."""
    if isinstance(param, click.Argument):
        assert isinstance(widget, (Input, PathField))
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

    assert isinstance(widget, (Input, PathField))
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


@dataclass
class FieldSpec:
    """One form field's presentation: label, widget, whether it's required, and its
    optional autocomplete companion (spec 004 US2)."""

    label: str
    widget: AnyFieldWidget
    required: bool
    autocomplete: SafePathAutoComplete | None = None


def _field_is_empty(widget: AnyFieldWidget) -> bool:
    if isinstance(widget, (Input, PathField)):
        return not widget.value.strip()
    if isinstance(widget, Select):
        return widget.value is Select.BLANK or widget.value in (None, "")
    if isinstance(widget, Checkbox):
        return False  # a boolean flag is never "empty"
    return False


def count_empty_required(specs: list[FieldSpec]) -> int:
    return sum(1 for spec in specs if spec.required and _field_is_empty(spec.widget))


def _frame_children(specs: list[FieldSpec]) -> list[Widget]:
    """No trailing "required" marker on individual labels -- required fields are
    already grouped under the "Required" frame, so a per-field marker would be
    redundant (spec 004 US2)."""
    children: list[Widget] = []
    for index, spec in enumerate(specs):
        if spec.label:
            children.append(Label(spec.label))
        if index < len(specs) - 1:
            spec.widget.styles.margin = (0, 0, 1, 0)
        children.append(spec.widget)
        if spec.autocomplete is not None:
            children.append(spec.autocomplete)
    return children


def build_field_frames(specs: list[FieldSpec]) -> list[Vertical]:
    """Build the required/optional frames (spec 004 US2): required frame first (solid
    red border, live "N remaining" subtitle), optional frame second (solid blue
    border). Each frame gets a 1-character margin/padding and sizes to its content
    (rather than expanding to fill the screen). A group with no fields produces no
    frame for that group (FR-004)."""
    frames: list[Vertical] = []
    required_specs = [spec for spec in specs if spec.required]
    optional_specs = [spec for spec in specs if not spec.required]

    if required_specs:
        frame = Vertical(*_frame_children(required_specs), id="required-frame")
        frame.styles.border = ("solid", "red")
        frame.border_title = "Required"
        frame.border_subtitle = f"{count_empty_required(specs)} remaining"
        frame.styles.height = "auto"
        frame.styles.margin = 1
        frame.styles.padding = 1
        frames.append(frame)

    if optional_specs:
        frame = Vertical(*_frame_children(optional_specs), id="optional-frame")
        frame.styles.border = ("solid", "blue")
        frame.border_title = "Optional"
        frame.styles.height = "auto"
        frame.styles.margin = 1
        frame.styles.padding = 1
        frames.append(frame)

    return frames


def refresh_required_subtitle(required_frame: Vertical, specs: list[FieldSpec]) -> None:
    """Recompute and re-set the required frame's "N remaining" subtitle (FR-004b)."""
    required_frame.border_subtitle = f"{count_empty_required(specs)} remaining"


def build_identity_frame(command: click.Command) -> Vertical:
    """Build the Command Identity block (spec 004 US6, shared by the command prep and
    command result screens): the command name in bold, its existing CLI description
    underneath -- the same source the menu's own entries use, shown in full (never
    ellipsis-ed) but capped at 3 lines so a long description can't push the rest of
    the screen down (FR-002c/FR-020). No border/title: borderless, just a bit of
    padding, so it doesn't compete visually with the field-group frames."""
    name_label = Label(command.name or "", id="identity-name")
    name_label.styles.text_style = "bold"

    description_label = Label(command.get_short_help_str(limit=10_000), id="identity-description")
    description_label.styles.width = "100%"
    description_label.styles.max_height = 3

    frame = Vertical(name_label, description_label, id="identity-frame")
    frame.styles.height = "auto"
    frame.styles.padding = (1, 2)
    return frame
