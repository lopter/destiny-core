import asyncio
import click
import os
import subprocess
import sys

from pathlib import Path
from typing import Optional

from multilab.backups import config, utils


@click.command(help="Restore the given backup on this host.")
@click.option(
    "--config-path", "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the configuration file that lists all backups.",
    default=Path("/etc/multilab-backups.json"),
    show_default=True,
    required=True,
)
@click.option(
    "--dest-path",
    type=click.Path(file_okay=False, path_type=Path),
    help=(
        "Restore the backup at this directory, defaults to the source path "
        "of the backup."
    ),
)
@click.argument("job_name")
def main(config_path: Path, dest_path: Optional[Path], job_name: str) -> None:
    cfg = config.Config.load(config_path)

    job_cfg = cfg.jobs_by_name.get(job_name)
    if job_cfg is None:
        msg = f"Could not find any backups named {job_name} in {config_path}"
        click.echo(msg, err=True)
        sys.exit(1)

    if job_cfg.type != config.BackupType.RESTIC_B2:
        msg = "Only restic-b2 backups can be restored at the moment"
        click.echo(msg, err=True)
        sys.exit(1)

    if dest_path is None:
        if job_cfg.direction == config.BackupDirection.PUSH:
            dest_path = job_cfg.local_path
        else:
            dest_path = job_cfg.remote_path
    assert dest_path is not None
    if not asyncio.run(utils.is_mounted(dest_path)):
        msg = f"The filesystem for {dest_path} must be mounted before restore"
        click.echo(msg, err=True)
        sys.exit(1)

    click.echo(f"Restoring latest restic snapshot to {dest_path}")
    subprocess.check_call(
        (
            "restic",
            "--repo", f"b2:{cfg.restic.b2.bucket}:{job_name}",
            "--password-file", str(job_cfg.password_path),
            "--cache-dir", str(cfg.restic.cache_dir),
            "restore",
            # You shouldn't actually set target: Restic backups include the
            # full realpath so that you restore does not need any path to be
            # specified. If you desire to restore a backup to a different path,
            # then you don't only need to know that new different path but also
            # the original path so that you can dereference it throught the
            # snapshotID:subfolder notation.
            "--target", str(dest_path),
            "latest"
        ),
        env=os.environ | {
            "B2_ACCOUNT_ID": cfg.restic.b2.key_id,
            "B2_ACCOUNT_KEY": cfg.restic.b2.application_key,
        },
    )
