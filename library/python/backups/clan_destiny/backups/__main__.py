import click
import logging

from pathlib import Path

from clan_destiny.backups import config, dump, restore


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
    ctx.obj = config.load(config_path)
    logging.basicConfig(level=logging.INFO)


main.add_command(dump.dump)
main.add_command(restore.restore)


if __name__ == "__main__":
    main()
