from ome_zarr_tools.core.config_registry import (
    CONFIGURABLE_VARIABLES,
    build_default_map,
    unrecognized_keys,
)


def test_shared_variables_resolve_to_both_from_images_and_migrate():
    for name in ("OME_ZARR_TOOLS_TARGET_VERSION", "OME_ZARR_TOOLS_CHUNKS_PER_SHARD"):
        variable = next(v for v in CONFIGURABLE_VARIABLES if v.name == name)
        commands = {target[0] for target in variable.targets}
        assert commands == {"from_images", "migrate"}


def test_num_levels_variables_resolve_to_exactly_one_target_each_and_never_cross_apply():
    by_command = {
        "OME_ZARR_TOOLS_FROM_IMAGES_NUM_LEVELS": "from_images",
        "OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS": "downsample",
        "OME_ZARR_TOOLS_UPSAMPLE_NUM_LEVELS": "upsample",
    }
    for name, expected_command in by_command.items():
        variable = next(v for v in CONFIGURABLE_VARIABLES if v.name == name)
        assert variable.targets == ((expected_command, "num_levels"),)

    mapping = build_default_map({"OME_ZARR_TOOLS_DOWNSAMPLE_NUM_LEVELS": "3"})
    assert mapping == {"downsample": {"num_levels": "3"}}


def test_unrecognized_keys_flags_unmatched_prefixed_key_but_ignores_others():
    values = {
        "OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE": "64",
        "OME_ZARR_TOOLS_TYPO_OPTION": "1",
        "AWS_ACCESS_KEY_ID": "abc",
    }
    unrecognized = unrecognized_keys(values)
    assert unrecognized == ["OME_ZARR_TOOLS_TYPO_OPTION"]


def test_build_default_map_is_nested_by_command_name():
    mapping = build_default_map(
        {
            "OME_ZARR_TOOLS_TARGET_VERSION": "0.5",
            "OME_ZARR_TOOLS_FROM_IMAGES_CHUNK_SIZE": "128",
        }
    )
    assert mapping == {
        "from_images": {"target_version": "0.5", "chunk_size": "128"},
        "migrate": {"target_version": "0.5"},
    }


def test_registry_has_exactly_thirteen_entries():
    assert len(CONFIGURABLE_VARIABLES) == 13


def test_no_apply_mask_temporary_upsample_variable():
    """FR-013: --temporary_upsample was removed, not made configurable."""
    assert not any("TEMPORARY_UPSAMPLE" in v.name for v in CONFIGURABLE_VARIABLES)


def test_no_migrate_chunk_size_variable():
    """FR-014: migrate does not gain --chunk_size; from_images's stays unscoped."""
    chunk_size_var = next(v for v in CONFIGURABLE_VARIABLES if v.name.endswith("CHUNK_SIZE"))
    assert chunk_size_var.targets == (("from_images", "chunk_size"),)
