import click
from click.testing import CliRunner

from ome_zarr_tools.core.click_ext import TuiOption


def test_tui_max_occurrences_is_stored_and_not_seen_by_click():
    @click.command()
    @click.option(
        "--corner", nargs=3, type=int, multiple=True, cls=TuiOption, tui_max_occurrences=2
    )
    def cmd(corner: tuple[tuple[int, ...], ...]) -> None:
        click.echo(str(corner))

    corner_param = next(p for p in cmd.params if p.name == "corner")
    assert isinstance(corner_param, TuiOption)
    assert corner_param.tui_max_occurrences == 2

    runner = CliRunner()
    result = runner.invoke(cmd, ["--corner", "0", "0", "0", "--corner", "1", "1", "1"])
    assert result.exit_code == 0, result.output
    assert "(0, 0, 0), (1, 1, 1)" in result.output


def test_tui_max_occurrences_defaults_to_none_when_unset():
    @click.command()
    @click.option("--output", cls=TuiOption)
    def cmd(output: str | None) -> None:
        pass

    output_param = next(p for p in cmd.params if p.name == "output")
    assert isinstance(output_param, TuiOption)
    assert output_param.tui_max_occurrences is None
