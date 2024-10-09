from __future__ import annotations

import dataclasses
import enum
import json

from typing import Any, Optional, Dict
from pathlib import Path

# The file was originally spit by ChatGPT, ideally we would have something
# smarter and more predictable to generate config loaders from Nix modules.


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

    def validate(self):
        if not self.bucket:
            raise ValueError("B2 bucket is required.")
        if not self.key_id:
            raise ValueError("B2 key ID is required.")
        if not self.application_key:
            raise ValueError("B2 application key is required.")


@dataclasses.dataclass
class Restic:
    cache_dir: Path
    b2: B2

    def validate(self):
        # if not self.cache_dir or not self.cache_dir.is_dir():
        #     raise ValueError("Restic cache directory is invalid or does not exist.")
        self.b2.validate()


@dataclasses.dataclass
class BackupJob:
    type: BackupType
    direction: BackupDirection
    local_host: str
    local_path: Path
    remote_host: Optional[str]
    remote_path: Optional[Path]
    one_file_system: bool
    public_key_path: Optional[Path]
    private_key_path: Optional[Path]
    password_path: Optional[Path]
    retention: Optional[str]

    def validate(self):
        if not self.local_host:
            raise ValueError("Local host is required.")
        if not self.local_path or not self.local_path.is_absolute():
            raise ValueError("Invalid or non-absolute local path.")

        if self.type == BackupType.RSYNC:
            if not self.remote_host:
                raise ValueError("Missing remote host.")
            if not self.remote_path:
                raise ValueError("Missing remote path.")
            if not not self.remote_path.is_absolute():
                raise ValueError("Invalid or non-absolute remote path.")
            if not self.public_key_path or not self.public_key_path.exists():
                raise ValueError("Missing or invalid public key path.")
            if not self.private_key_path or not self.private_key_path.exists():
                raise ValueError("Missing or invalid private key path.")
        elif self.type == BackupType.RESTIC_B2:
            if not self.retention:
                raise ValueError("Missing retention.")
            if not self.password_path or not self.password_path.exists():
                raise ValueError("Missing password path.")
            if self.direction != BackupDirection.PUSH:
                raise ValueError("Backups cannot be pulled with restic")


@dataclasses.dataclass
class Config:
    jobs_by_name: Dict[str, BackupJob]
    restic: Restic

    @classmethod
    def load(cls, filename: Path) -> Config:
        with filename.open('r') as file:
            data = json.load(file)
        jobs_by_name: dict[str, BackupJob] = {}
        for job_name, job_data in data["jobsByName"].items():
            job_args: dict[str, Any] = {}
            type = job_data["type"].upper().replace("-", "_")
            job_args["type"] = BackupType[type]
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
            public_key_path = job_data.get("publicKeyPath")
            job_args["one_file_system"] = job_data["oneFileSystem"]
            if public_key_path is not None:
                job_args["public_key_path"] = Path(public_key_path)
            else:
                job_args["public_key_path"] = None
            private_key_path = job_data.get("privateKeyPath")
            if private_key_path is not None:
                job_args["private_key_path"] = Path(private_key_path)
            else:
                job_args["private_key_path"] = None
            password_path = job_data.get("passwordPath")
            if password_path is not None:
                job_args["password_path"] = Path(password_path)
            else:
                job_args["password_path"] = None
            job_args["retention"] = job_data.get("retention")
            jobs_by_name[job_name] = BackupJob(**job_args)
        b2_details = data["restic"]["b2"]
        b2_key_id = Path(b2_details["keyIdPath"]).read_text().strip()
        b2_app_id = Path(b2_details["applicationKeyPath"]).read_text().strip()
        cfg = cls(
            jobs_by_name,
            Restic(
                cache_dir=Path(data["restic"]["cacheDir"]),
                b2=B2(
                    bucket=b2_details["bucket"],
                    key_id=b2_key_id,
                    application_key=b2_app_id,
                ),
            ),
        )
        cfg.validate()
        return cfg

    def validate(self):
        for job in self.jobs_by_name.values():
            job.validate()
        self.restic.validate()
