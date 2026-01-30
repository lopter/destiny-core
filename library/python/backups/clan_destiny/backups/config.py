import enum
import pydantic
import socket
import urllib.parse

from pathlib import Path
from typing import Annotated, Any, NamedTuple, override, Self


class BaseModel(pydantic.BaseModel):
    @staticmethod
    def _to_camel(snake: str) -> str:
        components = snake.split("_")
        return components[0] + "".join(word.capitalize() for word in components[1:])

    model_config = pydantic.ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        frozen=True,
        strict=True,
    )


class BackupType(enum.Enum):
    RESTIC_B2 = "restic-b2"
    RSYNC = "rsync"


class BackupDirection(enum.Enum):
    PUSH = "push"
    PULL = "pull"


class B2(BaseModel):
    bucket: str
    key_id_path: pydantic.FilePath
    application_key_path: pydantic.FilePath

    # Pre-computed values (set in model_post_init)
    key_id: str = pydantic.Field(default="", exclude=True)
    application_key: str = pydantic.Field(default="", exclude=True)

    @override
    def model_post_init(self, __context: Any) -> None:
        key_id = self.key_id_path.read_text().strip()
        object.__setattr__(self, "key_id", key_id)
        app_key = self.application_key_path.read_text().strip()
        object.__setattr__(self, "application_key", app_key)


class OpenBao(BaseModel):
    addr: str
    role_id_path: pydantic.FilePath
    secret_id_path: pydantic.FilePath
    auth_approle_path: str = "approle"
    tls_cacert: pydantic.FilePath | None = pydantic.Field(
        default=None,
        alias="tlsCaCert",
    )
    tls_server_name: str | None = None
    engine_path: str
    signer_role: str

    @pydantic.model_validator(mode="after")
    def derive_tls_server_name(self) -> Self:
        if self.tls_server_name is None:
            parts = urllib.parse.urlparse(self.addr)
            if parts.hostname is None:
                msg = (
                    f"tls_server_name not specified and cannot be derived "
                    f"from addr: {self.addr}"
                )
                raise ValueError(msg)
            object.__setattr__(self, "tls_server_name", parts.hostname)
        return self


class SSH(BaseModel):
    ca: OpenBao
    public_key_path: pydantic.FilePath
    private_key_path: pydantic.FilePath

    @property
    def public_key(self) -> Path:
        return self.public_key_path

    @property
    def private_key(self) -> Path:
        return self.private_key_path


class Restic(BaseModel):
    cache_dir: pydantic.DirectoryPath
    b2: B2


def _validate_absolute(path: str) -> str:
    if not path.startswith("/"):
        raise ValueError(f"path must be absolute, got: {path}")
    return path


AbsolutePath = Annotated[str, pydantic.AfterValidator(_validate_absolute)]


class BackupJob(BaseModel):
    type: BackupType
    direction: BackupDirection
    local_host: str
    local_path: AbsolutePath
    remote_host: str | None = None
    remote_path: AbsolutePath | None = None
    one_file_system: bool = True
    password_path: pydantic.FilePath | None = None
    retention: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_job_requirements(self) -> Self:
        if not self.local_host:
            raise ValueError("local_host is required")

        if self.type == BackupType.RSYNC:
            if not self.remote_host:
                raise ValueError("remote_host is required for rsync jobs")
            if not self.remote_path:
                raise ValueError("remote_path is required for rsync jobs")
        elif self.type == BackupType.RESTIC_B2:
            if not self.retention:
                raise ValueError("retention is required for restic-b2 jobs")
            if self.direction != BackupDirection.PUSH:
                raise ValueError("restic-b2 jobs only support push direction")
            if not self.password_path:
                raise ValueError("a password file is required for restic-b2 jobs")

        return self


class ValidationContext(NamedTuple):
    fqdn: str


class Config(BaseModel):
    jobs_by_name: dict[str, BackupJob] = pydantic.Field(default_factory=dict)
    restic: Restic | None = None
    ssh: SSH | None = None

    @pydantic.model_validator(mode="after")
    def validate_config_requirements(
        self,
        info: pydantic.ValidationInfo,
    ) -> Self:
        assert isinstance(info.context, ValidationContext)
        local_host = info.context.fqdn
        counts: dict[BackupType, int] = {t: 0 for t in BackupType}
        for job in self.jobs_by_name.values():
            counts[job.type] += 1 if job.local_host == local_host else 0

        restic_b2_count = counts[BackupType.RESTIC_B2]
        if restic_b2_count > 0 and self.restic is None:
            msg = (
                f"{restic_b2_count} restic-b2 job(s) configured but "
                f"restic config is missing"
            )
            raise ValueError(msg)

        rsync_count = counts[BackupType.RSYNC]
        if rsync_count > 0 and self.ssh is None:
            msg = (
                f"{rsync_count} rsync job(s) configured but "
                f"ssh config is missing"
            )
            raise ValueError(msg)

        return self


def load(filename: Path, fqdn: str | None = None) -> Config:
    context = ValidationContext(fqdn if fqdn is not None else socket.getfqdn())
    return Config.model_validate_json(filename.read_text(), context=context)
