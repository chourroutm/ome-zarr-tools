"""Top-level menu that launches a step-by-step wizard for any other subcommand.

Reuses each subcommand's own click ``Option``/``Argument`` definitions (introspected
from the parent group at runtime) rather than duplicating option metadata -- see
data-model.md § Command Session.
"""

from __future__ import annotations

import sys

import click

from ome_zarr_tools.core.errors import CliError


def _prompt_tokens(param: click.Parameter) -> list[str]:
    """Return the CLI tokens (e.g. ``["--threshold", "0.5"]``) for one parameter's answer."""
    if isinstance(param, click.Argument):
        value = click.prompt(param.human_readable_name)
        return [str(value)]

    assert isinstance(param, click.Option)
    flag = param.opts[0]

    if param.is_flag:
        if click.confirm(f"{flag}?", default=bool(param.default)):
            return [flag]
        return []

    if param.multiple:
        tokens: list[str] = []
        click.echo(f"{flag} (repeatable -- blank line to stop)")
        while True:
            prompt = f"  {param.nargs} values, space-separated" if param.nargs > 1 else "  value"
            raw = click.prompt(prompt, default="", show_default=False)
            if not raw.strip():
                break
            tokens.append(flag)
            tokens.extend(raw.split())
        return tokens

    if param.nargs and param.nargs > 1:
        prompt = f"{flag} ({param.nargs} values, space-separated)"
        raw = click.prompt(prompt, default="", show_default=False)
        return [flag, *raw.split()] if raw.strip() else []

    if param.required:
        value = click.prompt(flag)
        return [flag, str(value)]

    default = param.default
    default_str = "" if default is None else str(default)
    raw = click.prompt(flag, default=default_str, show_default=bool(default_str))
    return [flag, raw] if raw != "" else []


def _confirm_and_run(command: click.Command, tokens: list[str]) -> None:
    """Show the equivalent direct-CLI invocation, confirm, then run it.

    Shared by the prompt-based wizard and the Textual TUI (``interactive --tui``)
    so both give the identical no-side-effects-before-confirmation guarantee.
    """
    invocation = f"ome-zarr-tools {command.name} {' '.join(tokens)}".strip()
    click.echo(f"\nEquivalent command:\n  {invocation}")

    if not click.confirm("Run this now?", default=True):
        click.echo("Cancelled. No changes were made.")
        return

    command.main(args=tokens, prog_name=f"ome-zarr-tools {command.name}", standalone_mode=False)


def _run_wizard(command: click.Command) -> None:
    click.echo(f"\n--- {command.name} ---")
    if command.help:
        click.echo(command.help.strip().splitlines()[0])

    tokens: list[str] = []
    for param in command.params:
        tokens.extend(_prompt_tokens(param))

    _confirm_and_run(command, tokens)


def _sibling_commands(ctx: click.Context) -> dict[str, click.Command]:
    """The other commands registered on the parent group, excluding `interactive` itself."""
    group = ctx.parent.command if ctx.parent is not None else ctx.command
    return {
        name: cmd
        for name, cmd in group.commands.items()  # type: ignore[attr-defined]
        if name != "interactive"
    }


def _run_prompt_menu(choices: dict[str, click.Command]) -> None:
    names = sorted(choices)

    click.echo("Available commands:")
    for i, name in enumerate(names, start=1):
        click.echo(f"  {i}. {name}")

    selection = click.prompt(
        "Select a command",
        type=click.Choice([str(i) for i in range(1, len(names) + 1)] + names),
        show_choices=False,
    )
    selected_name = names[int(selection) - 1] if selection.isdigit() else selection
    _run_wizard(choices[selected_name])


def _run_tui(choices: dict[str, click.Command]) -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise CliError(
            "--tui requires an interactive terminal (stdin/stdout must be a tty); "
            "run `interactive` without --tui instead."
        )

    from ome_zarr_tools.tui.app import InteractiveTUIApp

    app = InteractiveTUIApp(choices)
    invocation = app.run()
    if invocation:
        # Reliable fallback for "Copy & exit": the clipboard-copy attempt
        # (OSC 52) silently fails on terminals/multiplexers that don't pass
        # it through (e.g. tmux/screen over SSH without `set-clipboard on`),
        # with no way for the app to detect that -- printed here every time,
        # once App.run() returning confirms the terminal is back to normal.
        click.echo(f"Copied invocation: {invocation}")


@click.command(name="interactive")
@click.option(
    "--tui",
    "use_tui",
    is_flag=True,
    help="Use the full-screen Textual interface instead of line-by-line prompts.",
)
@click.pass_context
def interactive(ctx: click.Context, use_tui: bool) -> None:
    """Choose a command from a menu, then answer prompts to run it."""
    choices = _sibling_commands(ctx)
    if use_tui:
        _run_tui(choices)
    else:
        _run_prompt_menu(choices)
