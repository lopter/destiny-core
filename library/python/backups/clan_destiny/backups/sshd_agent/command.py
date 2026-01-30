"""This command is run by sshd when it accepts a connection for a backup job.

"""

import click
import logging

from pathlib import Path

from . import auth_info

logger = logging.getLogger("backups.sshd_agent")


@click.command(help=__doc__)
@click.option("--ssh-client", envvar="SSH_CLIENT", required=True)
@click.option("--ssh-connection", envvar="SSH_CONNECTION", required=True)
@click.option(
    "--ssh-user-auth",
    envvar="SSH_USER_AUTH",
    required=True,
    type=click.Path(exists=True, readable=True, path_type=Path),
)
@click.pass_context
def sshd_agent(
    ctx: click.Context,
    ssh_client: str,
    ssh_connection: str,
    ssh_user_auth: Path,
) -> None:
    print(f"SSH_CLIENT={ssh_client}")
    print(f"SSH_CONNECTION={ssh_connection}")
    print(f"SSH_USER_AUTH={ssh_user_auth}")
    print(f"Client public key = {auth_info.parse(ssh_user_auth)}")
