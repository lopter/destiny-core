import click
import logging

from pathlib import Path

from . import client, server, types


@click.group()
@click.option(
    "--socket-name",
    required=True,
    show_default=True,
    help="Name of the socket passed by systemd",
    default="hass-pam-authenticate.socket",
)
@click.option(
    "--socket-path",
    required=True,
    show_default=True,
    help="Path of the socket created by systemd",
    default="/run/hass-pam-authenticate.sock",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.pass_context
def main(ctx: click.Context, socket_name: str, socket_path: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="[%(levelname)s] %(message)s",
    )
    ctx.obj = types.MainOptions(socket_name, socket_path)


main.add_command(server.server)
main.add_command(client.client)
