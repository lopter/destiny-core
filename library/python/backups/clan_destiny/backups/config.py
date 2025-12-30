import dataclasses
import enum
import json
import urllib

from typing import Any, Self
from pathlib import Path

# Refactoring notes:
#
# - Normalize naming: variable of type `Path` do
#   not need to have their name end in `_path`;
# - Entire parts of the config should be optional based on the type of jobs
#   that are defined and relevant for the host (having access to all the
#   defined jobs from all hosts is handy).


class BackupType(enum.Enum):
    RESTIC_B2 = "restic-b2"
    RSYNC = "rsync"


class BackupDirection(enum.Enum):
    PUSH = "push"
    PULL = "pull"


@dataclasses.dataclass
class B2:
    bucket: str
    key_id: str
    application_key: str

    def validate(self) -> None:
        if not self.bucket:
            raise ValueError("B2 bucket is required.")
        if not self.key_id:
            raise ValueError("B2 key ID is required.")
        if not self.application_key:
            raise ValueError("B2 application key is required.")


@dataclasses.dataclass
class OpenBao:
    addr: str
    role_id_path: Path
    secret_id_path: Path
    auth_approle_path: str
    tls_cacert: Path | None
    tls_server_name: str | None
    engine_path: str
    signer_role: str


@dataclasses.dataclass
class SSH:
    ca: OpenBao
    public_key: Path | None
    private_key: Path | None


@dataclasses.dataclass
class Restic:
    cache_dir: Path
    b2: B2

    def validate(self) -> None:
        # if not self.cache_dir or not self.cache_dir.is_dir():
        #     raise ValueError("Restic cache directory is invalid or does not exist.")
        self.b2.validate()


@dataclasses.dataclass
class BackupJob:
    type: BackupType
    direction: BackupDirection
    local_host: str
    local_path: Path
    remote_host: str | None
    remote_path: Path | None
    one_file_system: bool
    password_path: Path | None
    retention: str | None

    def validate(self) -> None:
        if not self.local_host:
            raise ValueError("Local host is required.")
        if not self.local_path or not self.local_path.is_absolute():
            raise ValueError("Invalid or non-absolute local path.")

        if self.type == BackupType.RSYNC:
            if not self.remote_host:
                raise ValueError("Missing remote host.")
            if not self.remote_path:
                raise ValueError("Missing remote path.")
            if not self.remote_path.is_absolute():
                raise ValueError("Invalid or non-absolute remote path.")
        elif self.type == BackupType.RESTIC_B2:
            if not self.retention:
                raise ValueError("Missing retention.")
            if not self.password_path or not self.password_path.exists():
                raise ValueError("Missing password path.")
            if self.direction != BackupDirection.PUSH:
                raise ValueError("Backups cannot be pulled with restic")


@dataclasses.dataclass
class Config:
    jobs_by_name: dict[str, BackupJob]
    restic: Restic
    ssh: SSH

    @classmethod
    def load(cls, filename: Path) -> Self:
        with filename.open("r") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            msg = f"The config contains a {type(data)} instead of a dict"
            raise ValueError(msg)

        known_keys = {"jobsByName", "restic", "ssh"}
        if len(extra_keys := set(data.keys()) - known_keys) > 0:
            key_list = ", ".join(str(k) for k in extra_keys)
            raise ValueError(f"Unknown entries in the config: {key_list}")

        if not isinstance(data.get("jobsByName"), dict):
            raise ValueError(
                f"Expected jobsByName to be a dict "
                f"in the config but got {type(data.get("jobsByName"))}"
            )

        restic_b2_job_count = 0
        rsync_job_count = 0
        jobs_by_name: dict[str, BackupJob] = {}
        for job_name, job_data in data["jobsByName"].items():
            if not isinstance(job_data, dict):
                raise ValueError(
                    f"Expected details for job {job_name} "
                    f"to be a dict but got {type(job_data)}"
                )
            job_args: dict[str, Any] = {}
            job_type = job_data.get("type", "").lower().replace("-", "_")
            if job_type not in BackupType:
                raise ValueError(f"Unkown type {job_type} for job {job_name}")
            job_args["type"] = BackupType[job_type.upper()]
            direction = job_data["direction"].upper().replace("-", "_")
            job_args["direction"] = BackupDirection[direction]
            job_args["local_host"] = job_data["localHost"]
            job_args["local_path"] = Path(job_data["localPath"])
            job_args["remote_host"] = job_data.get("remoteHost")
            remote_path = job_data.get("remotePath")
            if remote_path is not None:
                job_args["remote_path"] = Path(remote_path)
            else:
                job_args["remote_path"] = None
            password_path = job_data.get("passwordPath")
            if password_path is not None:
                job_args["password_path"] = Path(password_path)
            else:
                job_args["password_path"] = None
            job_args["retention"] = job_data.get("retention")
            job_args["one_file_system"] = job_data.get("oneFileSystem", True)

            backup_job = BackupJob(**job_args)
            restic_b2_job_count += int(backup_job.type == BackupType.RESTIC_B2)
            rsync_job_count += int(backup_job.type == BackupType.RSYNC)
            jobs_by_name[job_name] = backup_job

        b2_cfg = B2(bucket="n/a", key_id="n/a", application_key="n/a")
        restic_cfg = Restic(
            cache_dir=Path(),
            b2=b2_cfg,
        )
        if restic_b2_job_count:
            b2_details = data["restic"].get("b2")
            if not isinstance(b2_details, dict):
                raise ValueError(
                    f"{restic_b2_job_count} restic_b2 jobs configured but b2 "
                    f"credentials are missing in the configuration"
                )
            # TODO: Check that each key is present before unpacking it.
            restic_cfg.cache_dir = Path(data["restic"]["cacheDir"])
            b2_cfg.bucket = b2_details["bucket"]
            b2_cfg.key_id = Path(b2_details["keyIdPath"]).read_text().strip()
            b2_cfg.application_key = (
                Path(b2_details["applicationKeyPath"]).read_text().strip()
            )

        openbao_cfg = OpenBao(
            addr="",
            role_id_path=Path(),
            secret_id_path=Path(),
            auth_approle_path="approle",
            tls_server_name=None,
            tls_cacert=None,
            engine_path="",
            signer_role="",
        )
        if rsync_job_count:
            openbao_details = data["ssh"]["ca"]
            openbao_cfg.addr = openbao_details["addr"]
            openbao_cfg.role_id_path = Path(openbao_details["roleIdPath"])
            openbao_cfg.secret_id_path = Path(openbao_details["secretIdPath"])
            if auth_path := openbao_details.get("authApprolePath"):
                openbao_cfg.auth_approle_path = auth_path
            tls_server_name = openbao_details.get("tlsServerName")
            if tls_server_name is None:
                parts = urllib.parse.urlparse(openbao_cfg.addr)
                if parts.hostname is None:
                    raise ValueError(
                        f"An hostname must be specified on "
                        f"the OpenBao addr, got: {openbao_cfg.addr}"
                    )
                tls_server_name = parts.hostname
            openbao_cfg.tls_server_name = tls_server_name
            if tls_cacert := openbao_details.get("tlsCaCert"):
                openbao_cfg.tls_cacert = Path(tls_cacert)
                # NOTE: check that the path exists and can be read
            openbao_cfg.engine_path = openbao_details["enginePath"]
            openbao_cfg.signer_role = openbao_details["signerRole"]

        ssh = SSH(ca=openbao_cfg, public_key=None, private_key=None)
        if rsync_job_count:
            ssh_details = data["ssh"]
            ssh.public_key = Path(ssh_details["publicKeyPath"])
            ssh.private_key = Path(ssh_details["privateKeyPath"])

        cfg = cls(jobs_by_name, restic_cfg, ssh)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        restic_b2_job_count = 0
        for job in self.jobs_by_name.values():
            job.validate()
            if job.type == BackupType.RESTIC_B2:
                restic_b2_job_count += 1
        if restic_b2_job_count > 0:
            self.restic.validate()
