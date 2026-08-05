from ome_zarr_tools.io.ome_metadata import add_half_pixel_translations


def test_add_half_pixel_translations_anchors_level_0_at_zero():
    """ngff-spec's documented formula: translation_N = (scale_N - scale_0) / 2."""
    datasets = [
        {"path": "0", "coordinateTransformations": [{"type": "scale", "scale": [1.0, 1.0, 2.0]}]},
        {"path": "1", "coordinateTransformations": [{"type": "scale", "scale": [2.0, 2.0, 4.0]}]},
        {"path": "2", "coordinateTransformations": [{"type": "scale", "scale": [4.0, 4.0, 8.0]}]},
    ]

    result = add_half_pixel_translations(datasets)

    assert [t["type"] for t in result[0]["coordinateTransformations"]] == ["scale", "translation"]
    assert result[0]["coordinateTransformations"][1]["translation"] == [0.0, 0.0, 0.0]
    assert result[1]["coordinateTransformations"][1]["translation"] == [0.5, 0.5, 1.0]
    assert result[2]["coordinateTransformations"][1]["translation"] == [1.5, 1.5, 3.0]
    # scale itself is untouched.
    assert result[1]["coordinateTransformations"][0]["scale"] == [2.0, 2.0, 4.0]


def test_add_half_pixel_translations_replaces_any_existing_translation():
    datasets = [
        {
            "path": "0",
            "coordinateTransformations": [
                {"type": "scale", "scale": [1.0, 1.0]},
                {"type": "translation", "translation": [99.0, 99.0]},
            ],
        },
        {"path": "1", "coordinateTransformations": [{"type": "scale", "scale": [2.0, 2.0]}]},
    ]

    result = add_half_pixel_translations(datasets)

    assert result[0]["coordinateTransformations"][1]["translation"] == [0.0, 0.0]
    assert result[1]["coordinateTransformations"][1]["translation"] == [0.5, 0.5]


def test_add_half_pixel_translations_does_not_mutate_input():
    datasets = [
        {"path": "0", "coordinateTransformations": [{"type": "scale", "scale": [1.0]}]},
    ]
    original = [dict(d) for d in datasets]

    add_half_pixel_translations(datasets)

    assert datasets == original
