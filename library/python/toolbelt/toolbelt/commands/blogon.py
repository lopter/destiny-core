import ipaddress
import logging
import click
import multiprocessing
import subprocess

from pathlib import Path

from . import utils

logger = logging.getLogger("commands.blogon")

POP_SSH_PORT = 1103 # TODO: pull that from the Nix SoT
POP_HOSTNAME_PREFIX = "fly-io-pop"


@click.group(
    help=f"Manage my blog at http://louis.opter.org/"
)
def blogon() -> None:
    pass


@blogon.command(
    name="publish",
    help=f"Publish new blog posts.",
)
@click.pass_context
def publish(ctx: click.Context) -> None:
    def is_pop_machine(machine: utils.tailscale.Peer) -> bool:
        return machine.hostname.startswith(POP_HOSTNAME_PREFIX)
    machines = utils.tailscale.peers(filter_fn=is_pop_machine)
    logger.info(f"Got {len(machines)} machines")
    jobs = ((each,) for each in machines)
    with multiprocessing.Pool(processes=len(machines)) as workers:
        result = workers.starmap_async(rsync_posts, jobs)
        status = sum(1 if returncode > 0 else 0 for returncode in result.get())
    ctx.exit(status)


def rsync_posts(machine: utils.tailscale.Peer) -> int:
    ssh_cmd = (
        "ssh",
        f"-o Port={POP_SSH_PORT}",
        "-o User=blogon",
        "-o BatchMode=yes",  # never ask for something on stdin
        "-o Compression=no",  # we do it beforehand
        "-o ControlMaster=no",
        "-o VisualHostKey=no",
        "-o StrictHostKeyChecking=no", # We really need an ssh CA
    )
    src = f"{Path.home() / 'archives/blogon'}/"
    dst = f"{machine.ipv4}:/var/lib/blogon/"
    print("Tap the YubiKey")
    p = subprocess.run(
        [
            "rsync",
            "--archive",
            f"--rsh={' '.join(ssh_cmd)}",
            "--chown=blogon:blogon",
            "--exclude=/assets/**",
            src,
            dst,
        ]
    )
    machine_name = machine.dns_name.split(".")[0]
    if p.returncode == 0:
        logging.info(f"Machine {machine_name}: OK.")
        return 0
    logging.warning(f"Machine {machine_name}: error {p.returncode}")
    return p.returncode
