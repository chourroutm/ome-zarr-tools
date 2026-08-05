from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click

from ome_zarr_tools.core.errors import CliError

USER_CONFIG_REL = Path(".local") / "ome-zarr-tools.config"
PROJECT_CONFIG_NAME = "ome-zarr-tools.config"


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CliError(f"Failed to read config at {path} (invalid JSON): {exc}") from exc


def _write_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _target_path(user: bool, project: str | None) -> Path:
    if user:
        return Path.home() / USER_CONFIG_REL
    assert project is not None
    return Path(project).resolve() / PROJECT_CONFIG_NAME


def _parse_kv_pair(pair: str) -> tuple[str, Any]:
    if "=" not in pair:
        raise click.BadParameter(f"Expected key=value form, got: {pair!r}")
    key, val = pair.split("=", 1)
    key, val = key.strip(), val.strip()
    if val.lower() in ("true", "false"):
        return key, val.lower() == "true"
    if val.lower() in ("null", "none", ""):
        return key, None
    try:
        return key, int(val)
    except ValueError:
        pass
    try:
        return key, float(val)
    except ValueError:
        pass
    return key, val


@click.group()
def config() -> None:
    """Manage configuration for ome-zarr-tools.

    Config files:
      - User: $HOME/.local/ome-zarr-tools.config
      - Project: /path/to/project/ome-zarr-tools.config
    """


@config.command("show")
@click.option("--user", is_flag=True, help="Show only the user config.")
@click.option(
    "--project",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    help="Project directory whose config should be shown (defaults to cwd).",
)
def show(user: bool, project: str | None) -> None:
    """Show configuration. With neither flag, show a merged view (project overrides user)."""
    home = Path.home()
    user_path = home / USER_CONFIG_REL
    project_path = (Path(project).resolve() if project else Path.cwd()) / PROJECT_CONFIG_NAME

    user_cfg = _read_config(user_path)
    proj_cfg = _read_config(project_path)

    def _exists_note(p: Path) -> str:
        return "(exists)" if p.exists() else "(not found)"

    click.echo("Configuration files looked up:")
    click.echo(f"  user:    {user_path} {_exists_note(user_path)}")
    click.echo(f"  project: {project_path} {_exists_note(project_path)}")
    click.echo("")

    if user:
        click.echo("User config:")
        click.echo(json.dumps(user_cfg, indent=2) if user_cfg else "<none>")
        return

    if project:
        click.echo("Project config:")
        click.echo(json.dumps(proj_cfg, indent=2) if proj_cfg else "<none>")
        return

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
@click.option("--user", is_flag=True, help="Write to the user config.")
@click.option(
    "--project",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    help="Project directory to write the config to.",
)
@click.argument("pairs", nargs=-1, required=True)
def set_config(user: bool, project: str | None, pairs: Iterable[str]) -> None:
    """Set key=value pairs in the chosen config file.

    Examples:
      ome-zarr-tools config set --user compression=zstd
      ome-zarr-tools config set --project /path/to/project voxel_size=0.5
    """
    if user and project:
        raise CliError("Choose either --user or --project, not both.")
    if not (user or project):
        raise CliError("Pass either --user or --project to select which config to modify.")

    target_path = _target_path(user, project)
    cfg = _read_config(target_path)
    for pair in pairs:
        key, value = _parse_kv_pair(pair)
        cfg[key] = value
        click.echo(f"Set {key} = {value!r} in {target_path}")
    _write_config(target_path, cfg)
    click.echo(f"Wrote config to {target_path}")


@config.command("reset")
@click.option("--user", is_flag=True, help="Operate on the user config.")
@click.option(
    "--project",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    help="Project directory whose config should be modified.",
)
@click.option("--all", "remove_all", is_flag=True, help="Remove the entire config file.")
@click.argument("keys", nargs=-1, required=False)
def reset_config(user: bool, project: str | None, remove_all: bool, keys: Iterable[str]) -> None:
    """Reset (remove) keys from the chosen config file, or remove the whole file with --all."""
    if user and project:
        raise CliError("Choose either --user or --project, not both.")
    if not (user or project):
        raise CliError("Pass either --user or --project to select which config to modify.")

    target_path = _target_path(user, project)
    if not target_path.exists():
        click.echo(f"No config file at {target_path} to reset.")
        return

    if remove_all:
        target_path.unlink()
        click.echo(f"Removed config file {target_path}")
        return

    if not keys:
        raise CliError("Provide one or more keys to reset, or use --all to remove the file.")

    cfg = _read_config(target_path)
    removed = [k for k in keys if k in cfg]
    for k in removed:
        cfg.pop(k, None)
    _write_config(target_path, cfg)
    click.echo(f"Removed keys {removed} from {target_path}")
