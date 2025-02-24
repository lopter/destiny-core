import click
import logging

from . import client, server, types


@click.group()
@click.option(
    "--socket-path",
    required=True,
    show_default=True,
    default="/run/hass-pam-authenticate/server.sock",
)
@click.pass_context
def main(ctx: click.Context, socket_path: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="[%(levelname)s] %(message)s",
    )
    ctx.obj = types.MainOptions(socket_path)


main.add_command(server.server)
main.add_command(client.client)
