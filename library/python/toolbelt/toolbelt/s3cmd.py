import contextlib
import logging
import os
import subprocess
import tempfile

from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger("s3cmd")


class Config(NamedTuple):
    access_key: str
    secret_key: str
    host_base: str
    check_ssl_certificate: bool = True
    check_ssl_hostname: bool = True

    @contextlib.contextmanager
    def as_file(self):
        lines = [
            "[default]",
            f"host_bucket = %(bucket)s.{self.host_base}",
        ]
        lines.extend(f"{k} = {v}" for k, v in self._asdict().items())
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete_on_close=False,
            suffix="clan-destiny",
        ) as config_file:
            print(os.linesep.join(lines), file=config_file)
            config_file.close()
            yield Path(config_file.name)


def sync(config: Config, local_dir: Path, bucket: str, remote_dir: str) -> None:
    dest = os.path.join(bucket, remote_dir)
    logger.info(f"Syncing {local_dir} to {dest}")
    with config.as_file() as config_path:
        subprocess.check_call([
            "s3cmd",
            f"--config={config_path}",
            "--skip-existing",
            "--delete-removed",
            "sync",
            f"{local_dir}",
            f"s3://{dest}",
        ])


def delete(config: Config, bucket: str, remote_path: str) -> None:
    # Do not use `os.path.join` since remote_path can actually be `/`
    # (that is `/` is not necessarily a path separator):
    dest = f"s3://{bucket}/{remote_path}"
    logger.info(f"Deleting {dest}")
    with config.as_file() as config_path:
        subprocess.check_call([
            "s3cmd",
            f"--config={config_path}",
            "del",
            "--recursive",
            dest,
        ])
