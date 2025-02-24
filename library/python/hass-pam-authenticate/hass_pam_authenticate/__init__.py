import click
import os
import pexpect
import sys


@click.command()
def main() -> None:
    username = getenv("username")
    password = getenv("password")

    true_bin = pexpect.which("true")
    if not true_bin:
        click.echo("Could not find `true` in `PATH`", err=True)
        sys.exit(1)
    
    su = pexpect.spawn("su", ["-s", true_bin, username])
    su.expect("Password:")
    su.sendline(password)
    su.wait()
    su.close()
    sys.exit(su.exitstatus)


def getenv(var: str) -> str:
    if value := os.environ.get(var):
        return value
    click.echo(f"Could not get the {var} from the environment", err=True)
    sys.exit(1)
