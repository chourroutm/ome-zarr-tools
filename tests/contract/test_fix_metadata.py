from click.testing import CliRunner

from ome_zarr_tools.commands.fix_metadata import fix_metadata


def test_abort_leaves_dataset_unmodified(sample_ome_zarr):
    import zarr

    before = dict(zarr.open_group(str(sample_ome_zarr), mode="r").attrs)

    runner = CliRunner()
    result = runner.invoke(fix_metadata, [str(sample_ome_zarr)], input="\n\n\n\nn\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output

    after = dict(zarr.open_group(str(sample_ome_zarr), mode="r").attrs)
    assert before == after


def test_missing_path_is_an_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(fix_metadata, [str(tmp_path / "nonexistent.zarr")])
    assert result.exit_code != 0
