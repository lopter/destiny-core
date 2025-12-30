import contextlib
import logging
import os
import shlex
import shutil
import socket
import subprocess

from pathlib import Path
from typing import BinaryIO, IO, override, Self

from clan_destiny.backups import config, ssh_ca

from .rsync import RsyncCommands

logger = logging.getLogger("backups.dump.job")


class BackupResult:
    def __init__(self, tmp_dir: Path) -> None:
        self.tmp_dir: Path = tmp_dir
        self.stdout_fname: Path = tmp_dir / "stdout"
        self.stderr_fname: Path = tmp_dir / "stderr"
        self.return_code: None | int = None
        self.stdout: None | IO[bytes] = None
        self.stderr: None | IO[bytes] = None
        self.log: list[str] = []

    @classmethod
    def _call_gzip(cls, stdout: BinaryIO) -> subprocess.Popen[bytes]:
        gzip_cmd = ("gzip", "--best", "-c")
        return subprocess.Popen(gzip_cmd, stdin=subprocess.PIPE, stdout=stdout)

    @contextlib.contextmanager
    def tmp_capture_files(self):
        with (
            self.stdout_fname.open("wb") as ofp,
            self.stderr_fname.open("wb") as efp,
        ):
            gzip_stdout: subprocess.Popen[bytes] = self._call_gzip(ofp)
            gzip_stderr: subprocess.Popen[bytes] = self._call_gzip(efp)
            self.stdout = gzip_stdout.stdin
            self.stderr = gzip_stderr.stdin
            yield
            assert self.stdout is not None
            assert self.stderr is not None
            self.stdout.close()
            self.stderr.close()
            if (rc := gzip_stdout.wait()) > 0:
                logger.warning(f"gzip for stdout exit abnormally (status={rc})")
            if (rc := gzip_stderr.wait()) > 0:
                logger.warning(f"gzip for stderr exit abnormally (status={rc})")


class BackupJob:
    def __init__(
        self,
        tmp_dir: Path,
        name: str,
        type: config.BackupType,
    ) -> None:
        self.tmp_dir: Path = tmp_dir
        self.name: str = name
        self.type: config.BackupType = type

    @classmethod
    def from_name_and_config(
        cls,
        name: str,
        cfg: config.Config,
        tmp_dir: Path,
    ) -> Self:
        job = cfg.jobs_by_name[name]
        if job.type == config.BackupType.RSYNC:
            assert job.remote_path is not None
            assert job.remote_host is not None
            return RsyncBackupJob(
                tmp_dir=tmp_dir,
                name=name,
                type=job.type,
                local_path=job.local_path,
                remote_path=job.remote_path,
                remote_host=job.remote_host,
                direction=job.direction,
                ssh_config=cfg.ssh,
            )
        elif job.type == config.BackupType.RESTIC_B2:
            assert job.password_path is not None
            assert job.retention is not None
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
        name: str,
        type: config.BackupType,
        local_path: Path,
        remote_host: str,
        remote_path: Path,
        direction: config.BackupDirection,
        ssh_config: config.SSH,
    ) -> None:
        BackupJob.__init__(self, tmp_dir, name, type)
        if type != config.BackupType.RSYNC:
            raise ValueError(f"Expected an rsync backup job but got {type}")
        self.local_path: Path = local_path
        self.remote_host: str = remote_host
        self.remote_path: Path = remote_path
        self.ssh_ca: ssh_ca.Client = ssh_ca.Client(ssh_config)
        assert ssh_config.private_key is not None
        self.private_key: Path = ssh_config.private_key
        self.direction: config.BackupDirection = direction
        if direction == config.BackupDirection.PULL:
            os.makedirs(local_path, exist_ok=True)

    @override
    def run(self) -> BackupResult:
        result = BackupResult(self.tmp_dir)
        rsync_commander = RsyncCommands(
            self.remote_host,
            self.local_path,
            self.remote_path,
        )
        server_cmd = rsync_commander.server_mirror_copy(self.direction)
        certificate_id = f"{socket.gethostname()}-dump-{self.name}"
        with (
            self.ssh_ca.issue_cert(certificate_id, server_cmd) as certificate,
            result.tmp_capture_files(),
        ):
            cmd = rsync_commander.mirror_copy(
                self.direction,
                self.private_key,
                certificate,
            )
            result.log.append("INFO: rsync command: {}".format(" ".join(cmd)))
            try:
                _ = subprocess.check_call(
                    cmd,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
            except subprocess.CalledProcessError as ex:
                result.log.append("ERROR: rsync failed:\n\n{}".format(ex))
                result.return_code = ex.returncode
            else:
                result.return_code = 0
        return result

    @override
    def subject(self, status: str) -> str:
        return "{type} backup job #{name} {status} ({dir} by {host})".format(
            type=self.type.value,
            name=self.name,
            status=status,
            dir=self.direction.value,
            host=socket.gethostname(),
        )

    @override
    def setup_debug_script(self) -> None:
        rsync_commander = RsyncCommands(
            self.remote_host,
            self.local_path,
            self.remote_path,
        )
        server_cmd = rsync_commander.server_mirror_copy(self.direction)
        certificate_id = f"{socket.gethostname()}-debug-dump-{self.name}"
        with (
            self.ssh_ca.issue_cert(certificate_id, server_cmd) as certificate,
            (self.tmp_dir / "script.sh").open("wb") as fp,
        ):
            certificate_copy = self.tmp_dir / "ssh-cert.pub"
            _ = shutil.copy2(certificate, certificate_copy)
            cmd = rsync_commander.mirror_copy(
                self.direction,
                self.private_key,
                certificate_copy,
            )
            fp.write(shlex.join(cmd).encode())
            fp.write("\n".encode())


class ResticB2BackupJob(BackupJob):
    TAGS: frozenset[str] = frozenset(
        {
            "systemd_unit=clan-destiny-backups.service",
        }
    )

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
        self.repository: str = f"b2:{bucket}:{name}"
        self.local_path: Path = local_path
        self.password_path: Path = password_path
        self.one_file_system: bool = one_file_system
        self.retention: str = retention
        self.b2_key_id: str = restic_details.b2.key_id
        self.b2_application_key: str = restic_details.b2.application_key
        self.cache_dir: Path = restic_details.cache_dir

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
            written = fp.write(
                f"""#!/bin/sh
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
""".encode()
            )
            assert written > 0
        return script_path

    @override
    def run(self) -> BackupResult:
        result = BackupResult(self.tmp_dir)
        with result.tmp_capture_files():
            script_path = self._write_script()
            result.log.append(
                f"INFO: Executing {script_path}, see details in attached files."
            )
            try:
                _ = subprocess.check_call(
                    [str(script_path)],
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
            except subprocess.CalledProcessError as ex:
                result.log.append(f'ERROR: "{script_path}" failed:\n\n{ex}')
                result.return_code = ex.returncode
            else:
                result.return_code = 0
        return result

    @override
    def subject(self, status: str) -> str:
        return "{type} backup job #{name} {status} (push by {host})".format(
            type=self.type.value,
            name=self.name,
            status=status,
            host=socket.gethostname(),
        )

    @override
    def setup_debug_script(self) -> None:
        _ = self._write_script()
