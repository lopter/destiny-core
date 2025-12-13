import click
import logging

from . import (
    commands,
    mtrpacket as mtrpacket,
)


@click.group(help="Toolbelt to Monitor my Free connection")
def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="[%(levelname)s] %(message)s",
    )


main.add_command(commands.exporter)
