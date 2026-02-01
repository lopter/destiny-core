import click
import collections
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
@click.option(
    # Useful to validate the config in `checkPhase` when generating the
    # configuration at build time with `writeTextFile`.
    "--ignore-missing-paths/--no-ignore-missing-paths",
    help="Ignore validation errors for file that don't exists",
    default=False,
    show_default=True,
)
@click.pass_context
def validate_config(
    ctx: click.Context,
    fqdn: str,
    ignore_missing_paths: bool,
) -> None:
    try:
        _ = config.load(ctx.obj, fqdn)
    except pydantic.ValidationError as exc:
        errors = exc.errors()
        if ignore_missing_paths:
            def missing_path(etype: str) -> bool:
                return etype == "path_not_file" or etype == "path_not_directory"
            errors = [err for err in errors if not missing_path(err["type"])]
        if not errors:
            return
        click.echo(f"{len(errors)} validation errors in config for {fqdn}:")
        errors_by_loc = collections.defaultdict(list)
        for err in errors:
            loc = ".".join(str(component) for component in err["loc"])
            errors_by_loc[loc].append(err)
        for loc in errors_by_loc:
            click.echo(f"- {loc}:")
            for err in errors_by_loc[loc]:
                click.echo(f"  - {err["msg"]} (input_value={err["input"]})")
        ctx.exit(1)


main.add_command(dump.dump)
main.add_command(restore.restore)
main.add_command(sshd_agent.sshd_agent)


if __name__ == "__main__":
    main()
