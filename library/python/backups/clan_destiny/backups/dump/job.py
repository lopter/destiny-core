from __future__ import annotations

import contextlib
import os
import shlex
import socket
import subprocess

from pathlib import Path
from typing import (
    List,
    Union,
)

from clan_destiny.backups import config
from .rsync import RsyncCommands


class BackupResult(object):

    def __init__(self, tmp_dir: Path) -> None:
        self.tmp_dir = tmp_dir
        self.stdout_fname = tmp_dir / "stdout"
        self.stderr_fname = tmp_dir / "stderr"
        self.return_code = None  # type: Union[None, int]
        self.log = []  # type: List[str]

    @classmethod
    def _call_gzip(cls, stdout):
        gzip_cmd = ("gzip", "--best", "-c")
        return subprocess.Popen(gzip_cmd, stdin=subprocess.PIPE, stdout=stdout)

    @contextlib.contextmanager
    def tmp_capture_files(self):
        with open(self.stdout_fname, "wb") as ofp, \
                open(self.stderr_fname, "wb") as efp:
            self._gzip_stdout = self._call_gzip(stdout=ofp)
            self._gzip_stderr = self._call_gzip(stdout=efp)
            self.stdout = self._gzip_stdout.stdin
            self.stderr = self._gzip_stderr.stdin
            yield
            self.stdout.close()
            self.stderr.close()
            self._gzip_stdout.wait()
            self._gzip_stderr.wait()


class BackupJob:

    def __init__(
        self, tmp_dir: Path, name: str, type: config.BackupType,
    ) -> None:
        self.tmp_dir = tmp_dir
        self.name = name
        self.type = type

    @classmethod
    def from_name_and_config(
        cls,
        name: str,
        cfg: config.Config,
        tmp_dir: Path,
    ) -> BackupJob:
        job = cfg.jobs_by_name[name]
        if job.type == config.BackupType.RSYNC:
            return RsyncBackupJob(
                tmp_dir=tmp_dir,
                name=name,
                type=job.type,
                local_path=job.local_path,
                remote_path=job.remote_path,
                remote_host=job.remote_host,
                private_key_path=job.private_key_path,
                direction=job.direction,
            )
        elif job.type == config.BackupType.RESTIC_B2:
            return ResticB2BackupJob(
                tmp_dir=tmp_dir,
                name=name,
                type=job.type,
                local_path=job.local_path,
                password_path=job.password_path,
                one_file_system=job.one_file_system,
                retention=job.retention,
                restic_details=cfg.restic,
            )
        else:
            msg = f"{name} has unknonwn job type {job.type.value}"
            raise ValueError(msg)

    def run(self) -> BackupResult:
        raise NotImplementedError

    def subject(self, status: str) -> str:
        raise NotImplementedError

    def setup_debug_script(self) -> None:
        raise NotImplementedError


class RsyncBackupJob(BackupJob):

    def __init__(
        self,
        tmp_dir: Path,
        name,  # type: str
        type: config.BackupType,
        local_path: Path,
        remote_host,  # type: str
        remote_path: Path,
        private_key_path: Path,
        direction: config.BackupDirection,
    ) -> None:
        BackupJob.__init__(self, tmp_dir, name, type)
        if type != config.BackupType.RSYNC:
            raise ValueError(f"Expected an rsync backup job but got {type}")
        self.local_path = local_path
        self.remote_host = remote_host
        self.remote_path = remote_path
        self.private_key_path = private_key_path
        self.direction = direction
        if direction == config.BackupDirection.PULL:
            os.makedirs(local_path, exist_ok=True)

    def run(self):  # type: () -> BackupResult
        result = BackupResult(self.tmp_dir)
        with result.tmp_capture_files():
            cmd = RsyncCommands(
                remote_host=self.remote_host,
                local_path=self.local_path,
                remote_path=self.remote_path,
            ).mirror_copy(self.direction.value, self.private_key_path)
            result.log.append("INFO: rsync command: {}".format(" ".join(cmd)))
            try:
                subprocess.check_call(cmd, stdout=result.stdout, stderr=result.stderr)
            except subprocess.CalledProcessError as ex:
                result.log.append("ERROR: rsync failed:\n\n{}".format(ex))
                result.return_code = ex.returncode
            else:
                result.return_code = 0
        return result

    def subject(self, status: str) -> str:
        return "{type} backup job #{name} {status} ({dir} by {host})".format(
            type=self.type.value,
            name=self.name,
            status=status,
            dir=self.direction.value,
            host=socket.gethostname(),
        )

    def setup_debug_script(self) -> None:
        cmds = [RsyncCommands(
            remote_host=self.remote_host,
            local_path=self.local_path,
            remote_path=self.remote_path,
        ).mirror_copy(self.direction.value, self.private_key_path)]

        with (self.tmp_dir / "script.sh").open("wb") as fp:
            for cmd in cmds:
                escaped_args = (shlex.quote(arg) for arg in cmd)
                fp.write(" ".join(escaped_args).encode())
                fp.write("\n".encode())


class ResticB2BackupJob(BackupJob):

    TAGS = frozenset({"systemd_unit=clan-destiny-backups.service"})

    def __init__(
        self,
        tmp_dir: Path,
        name: str,
        type: config.BackupType,
        local_path: Path,
        password_path: Path,
        one_file_system: bool,
        retention: str,
        restic_details: config.Restic,
    ) -> None:
        BackupJob.__init__(self, tmp_dir, name, type)
        bucket = restic_details.b2.bucket
        self.repository = f"b2:{bucket}:{name}"
        self.local_path = local_path
        self.password_path = password_path
        self.one_file_system = one_file_system
        self.retention = retention
        self.b2_key_id = restic_details.b2.key_id
        self.b2_application_key = restic_details.b2.application_key
        self.cache_dir = restic_details.cache_dir

    def _write_script(self) -> Path:
        local_path = shlex.quote(str(self.local_path))
        cache_dir = shlex.quote(str(self.cache_dir))
        tag_options = " ".join(f"--tag {tag}" for tag in self.TAGS)
        if self.one_file_system is True:
            one_file_system_option = "--one-file-system"
        else:
            one_file_system_option = ""
        script_path = self.tmp_dir / "script.sh"
        with script_path.open("wb") as fp:
            os.fchmod(fp.fileno(), 0o750)
            fp.write(f"""#!/bin/sh
export B2_ACCOUNT_ID={self.b2_key_id}
export B2_ACCOUNT_KEY={self.b2_application_key}
set -x
restic() {{
    command restic                              \\
        --repo {self.repository}                \\
        --password-file {self.password_path}    \\
        --cache-dir {cache_dir}                 \\
        "$@"
}}
restic snapshots 2>&- || {{
    restic --quiet init || exit 1;
}}
restic --quiet backup {tag_options} {one_file_system_option} {local_path}
restic --quiet forget {tag_options} --prune --keep-within {self.retention}
restic --quiet check
""".encode())
        return script_path

    def run(self) -> BackupResult:
        result = BackupResult(self.tmp_dir)
        with result.tmp_capture_files():
            script_path = self._write_script()
            result.log.append(
                f"INFO: Executing {script_path}, "
                f"see details in attached files."
            )
            try:
                subprocess.check_call(
                    [str(script_path)], stdout=result.stdout, stderr=result.stderr,
                )
            except subprocess.CalledProcessError as ex:
                result.log.append(f"ERROR: \"{script_path}\" failed:\n\n{ex}")
                result.return_code = ex.returncode
            else:
                result.return_code = 0
        return result

    def subject(self, status: str) -> str:
        return "{type} backup job #{name} {status} (push by {host})".format(
            type=self.type.value,
            name=self.name,
            status=status,
            host=socket.gethostname(),
        )

    def setup_debug_script(self) -> None:
        self._write_script()
