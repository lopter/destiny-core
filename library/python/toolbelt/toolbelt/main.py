import click
import logging


@click.group(help="Toolbelt for multilab")
@click.pass_context
def main(_: click.Context) -> None:
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="[%(levelname)s] %(message)s",
    )
