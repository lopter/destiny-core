import contextlib
import hvac
import requests
import shlex
import tempfile

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import override

from clan_destiny.backups import config

__all__ = (
    "Client",
    "Error",
)


class Client:
    def __init__(self, cfg: config.SSH):
        session = requests.Session()

        # Setup TLS with custom CA & SNI if configured:
        if cfg.ca.tls_server_name or cfg.ca.tls_cacert:
            adapter = TLSAdapter(cfg.ca.tls_server_name, cfg.ca.tls_cacert)
            session.mount("https://", adapter)

        self._vault: hvac.Client = hvac.Client(url=cfg.ca.addr, session=session)
        self._vault.auth.approle.login(
            cfg.ca.role_id_path.read_text(),
            cfg.ca.secret_id_path.read_text(),
            mount_point=cfg.ca.auth_approle_path,
        )

        assert cfg.public_key is not None
        self._public_key: Path = cfg.public_key
        self._signer_role: str = cfg.ca.signer_role
        self._mount_point: str = cfg.ca.engine_path

    @contextlib.contextmanager
    def issue_cert(
        self,
        id: str,
        command: Sequence[str],
        valid_principals: Iterable[str] = ("root",),
    ) -> Iterator[Path]:
        response = self._vault.secrets.ssh.sign_ssh_key(
            self._signer_role,
            self._public_key.read_text(),
            ttl="1d",
            valid_principals=",".join(valid_principals),
            cert_type="user",
            key_id=id,
            # In a future iteration of this we can implement some kind of
            # well-known command to be executed server (sshd) side so that
            # we can truly force a (static) command here. The command would
            # then receive a "rpc call" on stdin with the job name, then
            # generate and execute the appropriate commands based on that. This
            # would increase security since the signer_role we use here
            # wouldn't be able to generate arbitrary commands anymore. The
            # server could also use the `SSH_CLIENT` and `SSH_CONNECTION` to
            # authenticate the client based on its source IP. If we set
            # `ExposeAuthInfo` in `sshd_config` we could also authenticate the
            # client based on its identity, and we could juste use the host
            # keys as the *client-side* authentication.
            critical_options={
                # I wonder if the way the command gets
                # shell-escaped matters to sshd:
                "force-command": shlex.join(command),
            },
            mount_point=self._mount_point,
        )
        if not isinstance(response, dict):
            msg = (
                f"Could not issue certificate, sign_ssh_key failed with "
                f"{response.status_code} {response.reason}: {response.text}"
            )
            raise Error(msg)

        signed_key = response["data"]["signed_key"]
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            prefix="clan-destiny-backups",
        ) as certificate:
            assert certificate.write(signed_key) == len(signed_key)
            certificate.flush()
            yield Path(certificate.name)


class Error(Exception):
    pass


class TLSAdapter(requests.adapters.HTTPAdapter):
    def __init__(
        self,
        server_name: str | None,
        ca_certs: Path | None,
        *args,
        **kwargs,
    ) -> None:
        msg = "At least one of server_name or ca_certs must be set"
        assert ca_certs or server_name, msg

        self.server_name = server_name
        self.ca_certs = ca_certs
        super().__init__(*args, **kwargs)

    @override
    def cert_verify(self, conn, url, verify, cert):
        # The implementation from `requests.adapters.HTTPAdapter` overrides
        # ca_certs on the connection returned by the poolmanager for some
        # reason. It seems to only apply for a situation with a (client) cert.
        #
        # I don't quite understand how it even worked before.
        pass

    @override
    def init_poolmanager(self, *args, **kwargs):
        if self.server_name:
            kwargs["server_hostname"] = self.server_name
        if self.ca_certs:
            kwargs["ca_certs"] = str(self.ca_certs)
        return super().init_poolmanager(*args, **kwargs)
