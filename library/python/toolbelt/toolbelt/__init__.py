import click
import logging

from . import commands


@click.group(help="Toolbelt for clan-destiny")
@click.pass_context
def main(_: click.Context) -> None:
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="[%(levelname)s] %(message)s",
    )


main.add_command(commands.blogon)
main.add_command(commands.pentosaurus)
main.add_command(commands.pikvm)
main.add_command(commands.vault)
