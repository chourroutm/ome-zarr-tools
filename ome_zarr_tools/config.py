import click

@click.command()
@click.argument("action", type=click.Choice(["show", "set", "reset"]))
@click.option("--key", default=None, help="Configuration key")
@click.option("--value", default=None, help="Configuration value (for 'set' action)")
def config(action, key, value):
    """
    Manage configuration for ome-zarr-tools.

    ACTION: show, set, reset
    """
    if action == "show":
        click.echo(f"Showing configuration for key: {key}")
        # TODO: Show config logic
    elif action == "set":
        click.echo(f"Setting configuration {key} to {value}")
        # TODO: Set config logic
    elif action == "reset":
        click.echo(f"Resetting configuration for key: {key}")
        # TODO: Reset config logic
