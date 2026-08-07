"""Regression guard for contracts/shortcut-contract.md (spec 003, User Story 1).

Every per-command screen's BINDINGS must start with the same six shared
shortcuts, in the same key/action order, sourced from
``ome_zarr_tools.tui.shortcuts.shared_bindings``.
"""

from ome_zarr_tools.tui.app import CommandFormScreen
from ome_zarr_tools.tui.screens.config_screen import ConfigScreen
from ome_zarr_tools.tui.screens.inspect_screen import InspectScreen
from ome_zarr_tools.tui.screens.metadata_screen import FixMetadataScreen, MigrateScreen
from ome_zarr_tools.tui.shortcuts import shared_bindings

_SHARED_KEY_ACTION_PAIRS = [(b.key, b.action) for b in shared_bindings()]


def _key_action_pairs(bindings) -> list[tuple[str, str]]:  # noqa: ANN001
    return [(b.key, b.action) for b in bindings]


def test_shared_shortcut_prefix_matches_every_per_command_screen():
    screens = (CommandFormScreen, InspectScreen, FixMetadataScreen, MigrateScreen, ConfigScreen)
    for screen_cls in screens:
        prefix = _key_action_pairs(screen_cls.BINDINGS)[: len(_SHARED_KEY_ACTION_PAIRS)]
        assert prefix == _SHARED_KEY_ACTION_PAIRS, screen_cls.__name__


def test_config_screen_overrides_only_the_primary_label():
    run_binding = ConfigScreen.BINDINGS[0]
    assert run_binding.key == "f5"
    assert run_binding.action == "run"
    assert run_binding.description == "Save"


def test_every_prep_screen_appends_restore_defaults_after_the_shared_set():
    """Spec 004 FR-027: Restore Defaults (F4) is appended after the shared prefix on
    every prep screen -- not baked into `shared_bindings()` itself, since the Command
    Result screen (spec 004 US7) reuses the shared prefix too but has no Restore
    Defaults action of its own."""
    screens = (CommandFormScreen, InspectScreen, FixMetadataScreen, MigrateScreen, ConfigScreen)
    for screen_cls in screens:
        extra = _key_action_pairs(screen_cls.BINDINGS[len(_SHARED_KEY_ACTION_PAIRS) :])
        assert ("f4", "restore_defaults") in extra, screen_cls.__name__


def test_shared_bindings_default_label_is_run():
    assert shared_bindings()[0].description == "Run"
