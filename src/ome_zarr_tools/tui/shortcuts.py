"""The shared shortcut set every per-command TUI screen exposes.

See specs/003-tui-menu-consistency/contracts/shortcut-contract.md -- this is
the single source of truth that contract implements.
"""

from __future__ import annotations

from textual.binding import Binding


def shared_bindings(primary_label: str = "Run") -> list[Binding]:
    """Return the six shared shortcuts every per-command screen exposes, in order.

    Only the primary action's label may vary per screen (e.g. "Save" for
    ``config``); its key and action name never change.
    """
    return [
        Binding("f5", "run", primary_label),
        Binding("f6", "copy", "Copy"),
        Binding("f7", "copy_and_exit", "Copy & exit"),
        Binding("f8", "toggle_log", "Log"),
        Binding("escape", "back", "Back to menu"),
        Binding("ctrl+c", "cancel", "Cancel"),
    ]
