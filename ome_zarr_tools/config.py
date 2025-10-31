import json
from pathlib import Path
from typing import Dict, Any, Iterable, Optional, Tuple

import click

USER_CONFIG_REL = Path(".local") / "ome-zarr-tools.config"
PROJECT_CONFIG_NAME = "ome-zarr-tools.config"


def _read_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise click.ClickException(f"Failed to read config at {path!s} (invalid JSON)")


def _write_config(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_kv_pair(pair: str) -> Tuple[str, Any]:
    if "=" not in pair:
        raise click.BadParameter(f"Expected key=value form, got: {pair!r}")
    key, val = pair.split("=", 1)
    key = key.strip()
    val = val.strip()
    if val.lower() in ("true", "false"):
        return key, val.lower() == "true"
    if val.lower() in ("null", "none", ""):
        return key, None
    try:
        ival = int(val)
        return key, ival
    except Exception:
        pass
    try:
        fval = float(val)
        return key, fval
    except Exception:
        pass
    return key, val


@click.group()
def config():
    """
    Manage configuration for ome-zarr-tools.

    Config files:
      - User: $HOME/.local/ome-zarr-tools.config
      - Project: /path/to/project/ome-zarr-tools.config

    Use subcommands: show, set, reset.
    """
    pass


@config.command("show")
@click.option(
    "--user",
    is_flag=True,
    help="Show only the user config at $HOME/.local/ome-zarr-tools.config",
)
@click.option(
    "--project",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    help="Project directory whose ome-zarr-tools.config should be shown (defaults to cwd when omitted).",
)
def show(user: bool, project: Optional[str]):
    """
    Show configuration. If neither --user nor --project is provided a merged view
    is displayed (project overrides user).
    """
    home = Path.home()
    user_path = home / USER_CONFIG_REL
    if project:
        project_path = Path(project).resolve() / PROJECT_CONFIG_NAME
    else:
        project_path = Path.cwd() / PROJECT_CONFIG_NAME

    user_cfg = _read_config(user_path) if user_path.exists() else {}
    proj_cfg = _read_config(project_path) if project_path.exists() else {}

    if user and project:
        click.echo("Both --user and --project given; showing both separately.")
    click.echo("Configuration files looked up:")
    click.echo(f"  user:    {user_path} {'(exists)' if user_path.exists() else '(not found)'}")
    click.echo(f"  project: {project_path} {'(exists)' if project_path.exists() else '(not found)'}")
    click.echo("")

    if user:
        click.echo("User config:")
        click.echo(json.dumps(user_cfg, indent=2) if user_cfg else "<none>")
        return

    if project:
        click.echo("Project config:")
        click.echo(json.dumps(proj_cfg, indent=2) if proj_cfg else "<none>")
        return

    # merged view
    merged = {**user_cfg, **proj_cfg}
    click.echo("User config:")
    click.echo(json.dumps(user_cfg, indent=2) if user_cfg else "<none>")
    click.echo("")
    click.echo("Project config:")
    click.echo(json.dumps(proj_cfg, indent=2) if proj_cfg else "<none>")
    click.echo("")
    click.echo("Merged configuration (project overrides user):")
    click.echo(json.dumps(merged, indent=2) if merged else "<none>")


@config.command("set")
@click.option(
    "--user",
    is_flag=True,
    help="Write to the user config at $HOME/.local/ome-zarr-tools.config",
)
@click.option(
    "--project",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    help="Project directory to write /path/to/project/ome-zarr-tools.config",
)
@click.argument("pairs", nargs=-1, required=True)
def set_config(user: bool, project: Optional[str], pairs: Iterable[str]):
    """
    Set key=value pairs in the chosen config file.

    Examples:
      ome-zarr-tools config set --user compression=zstd level=2
      ome-zarr-tools config set --project /path/to/project voxel_size=0.5
    """
    if user and project:
        raise click.UsageError("Please choose either --user or --project when setting configuration (not both).")
    if not (user or project):
        raise click.UsageError("When using 'set' you must pass either --user or --project to select which config to modify.")

    home = Path.home()
    target_path = (home / USER_CONFIG_REL) if user else (Path(project).resolve() / PROJECT_CONFIG_NAME)
    cfg = _read_config(target_path)
    for pair in pairs:
        key, value = _parse_kv_pair(pair)
        cfg[key] = value
        click.echo(f"Set {key} = {value!r} in {target_path}")
    _write_config(target_path, cfg)
    click.echo(f"Wrote config to {target_path}")


@config.command("reset")
@click.option(
    "--user",
    is_flag=True,
    help="Operate on the user config at $HOME/.local/ome-zarr-tools.config",
)
@click.option(
    "--project",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    help="Project directory whose config should be modified",
)
@click.option(
    "--all",
    "remove_all",
    is_flag=True,
    help="Remove the entire config file instead of individual keys.",
)
@click.argument("keys", nargs=-1, required=False)
def reset_config(user: bool, project: Optional[str], remove_all: bool, keys: Iterable[str]):
    """
    Reset (remove) keys from the chosen config file, or remove the whole file with --all.

    Examples:
      ome-zarr-tools config reset --project /path/to/project compression
      ome-zarr-tools config reset --user --all
    """
    if user and project:
        raise click.UsageError("Please choose either --user or --project when resetting configuration (not both).")
    if not (user or project):
        raise click.UsageError("When using 'reset' you must pass either --user or --project to select which config to modify.")

    home = Path.home()
    target_path = (home / USER_CONFIG_REL) if user else (Path(project).resolve() / PROJECT_CONFIG_NAME)
    if not target_path.exists():
        click.echo(f"No config file at {target_path} to reset.")
        return

    if remove_all:
        target_path.unlink()
        click.echo(f"Removed config file {target_path}")
        return

    if not keys:
        raise click.UsageError("Provide one or more keys to reset, or use --all to remove the file.")

    cfg = _read_config(target_path)
    removed = []
    for k in keys:
        if k in cfg:
            cfg.pop(k, None)
            removed.append(k)
    _write_config(target_path, cfg)
    click.echo(f"Removed keys {removed} from {target_path}")
