import click
import logging
import pydantic
import socket

from pathlib import Path

from clan_destiny.backups import (
    config,
    dump,
    restore,
    sshd_agent,
)


@click.group(help="Dump and restore backups using rsync or restic.")
@click.option(
    "--config-path",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the configuration file that lists all backups.",
    default=Path("/etc/clan-destiny-backups.json"),
    show_default=True,
    required=True,
)
@click.pass_context
def main(ctx: click.Context, config_path: Path) -> None:
    logging.basicConfig(level=logging.INFO)
    if ctx.invoked_subcommand == "validate-config":
        ctx.obj = config_path
        return
    ctx.obj = config.load(config_path)


@main.command(help="Validate the config for the given host.")
@click.option(
    "--fqdn", "-f",
    help="FQDN for the \"local host\"",
    default=socket.getfqdn(),
    show_default=True,
)
@click.pass_context
def validate_config(ctx: click.Context, fqdn: str) -> None:
    try:
        _ = config.load(ctx.obj, fqdn)
    except pydantic.ValidationError as ex:
        print(f"Invalid config for {fqdn}: {ex}")
        ctx.exit(1)


main.add_command(dump.dump)
main.add_command(restore.restore)
main.add_command(sshd_agent.sshd_agent)


if __name__ == "__main__":
    main()
