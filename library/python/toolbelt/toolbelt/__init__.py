import click
import logging

from . import (
    pentosaurus,
    vault,
)


@click.group(help="Toolbelt for clan-destiny")
@click.pass_context
def main(_: click.Context) -> None:
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="[%(levelname)s] %(message)s",
    )


main.add_command(pentosaurus.pentosaurus)
main.add_command(vault.vault)
