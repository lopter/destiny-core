import asyncio
import click
import socket

from pathlib import Path
from typing import cast

from clan_destiny.backups import config, dump, utils


def _get_config(ctx: click.Context) -> config.Config:
    return cast(config.Config, ctx.obj)


@click.group(help="Toolbelt to perform backups.")
@click.option(
    "--config-path", "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the configuration file that lists all backups.",
    default=Path("/etc/clan-destiny-backups.json"),
    show_default=True,
    required=True,
)
@click.pass_context
def main(ctx: click.Context, config_path: Path) -> None:
    ctx.obj = config.Config.load(config_path)


@main.command(
    help=(
        "Load the configuration and generates an authorized keys file for "
        "OpenSSH to accept backups from remote hosts."
    ),
)
@click.pass_context
def generate_root_authorized_keys(ctx: click.Context) -> None:
    host_aliases = (socket.getfqdn(),)
    dump.generate_root_authorized_keys(_get_config(ctx), host_aliases)


@main.command(help="Make sure the given path is mounted")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_context
def is_mounted(ctx: click.Context, path) -> None:
    ctx.exit(0 if asyncio.run(utils.is_mounted(path)) else 1)


@main.command(help=(
    "Given the name of a backup job setup a script "
    "to manually debug or run a backup for it."
))
@click.argument("job_name")
@click.pass_context
def setup_debug_script(ctx: click.Context, job_name: str) -> None:
    path = dump.setup_debug_script(_get_config(ctx), job_name, socket.getfqdn())
    click.echo(f"A manual backup script has been written to {path}.\n")
    click.echo(f"Do not forget to delete this directory once you are done.")


@main.command(help="Dump all backups defined for this host.")
@click.pass_context
def run(ctx: click.Context) -> None:
    dump.run(_get_config(ctx), socket.getfqdn())


main()
