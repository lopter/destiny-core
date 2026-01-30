import contextlib
import errno
import functools
import json
import os
import pwd
import pytest
import random
import re
import shutil
import socket
import string
import subprocess
import sys
import time
import threading

from collections.abc import Generator
from concurrent.futures import Future
from pathlib import Path
from typing import Any, NamedTuple, Self

from clan_destiny.backups import config, ssh_ca


TESTS_DIR = Path(__file__).parent
ENGINE_PATH = "ssh-backups-ca"
SIGNER_ROLE = "backups-dump"


_LISTENER_PATTERN = re.compile(
    r"core\.cluster-listener\.tcp: starting listener: listener_address=([^:]+):(\d+)"
)


class SSHKeyPair(NamedTuple):
    pub: str
    pub_path: Path
    priv: str
    priv_path: Path

    @classmethod
    def generate(cls, tmp_dir: Path, name: str) -> Self:
        priv_path = tmp_dir / name
        pub_path = tmp_dir / f"{name}.pub"
        _ = subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-C",
                f"Test {name}",
                "-N",
                "",
                "-f",
                str(priv_path),
            ],
            check=True,
            capture_output=True,
        )
        return cls(
            pub=pub_path.read_text(),
            pub_path=pub_path,
            priv=priv_path.read_text(),
            priv_path=priv_path,
        )


@pytest.fixture
def ssh_ca_keys(tmp_path: Path) -> SSHKeyPair:
    return SSHKeyPair.generate(tmp_path, name="ssh-ca")


@pytest.fixture
def test_username() -> str:
    return pwd.getpwuid(os.getuid()).pw_name


@pytest.fixture
def openbao_ssh_ca(
    tmp_path: Path,
    ssh_ca_keys: SSHKeyPair,
    test_username: str,
) -> Generator[config.OpenBao, None, None]:
    root_token = "root-token"
    approle_name = "backup-client"
    policy_name = "backup-ssh-signer"

    def openbao_addr_snooper() -> None:
        assert openbao.stderr is not None
        for line in openbao.stderr:
            _ = sys.stderr.write(line)
            _ = sys.stderr.flush()
            if addr_future.done():
                continue
            if (match := _LISTENER_PATTERN.search(line)) is not None:
                host = match.group(1)
                cluster_port = int(match.group(2))
                api_port = cluster_port - 1
                addr_future.set_result(f"http://{host}:{api_port}")

    cmd = [
        "bao",
        "server",
        "-dev",
        f"-dev-root-token-id={root_token}",
        "-dev-listen-address=127.0.0.1:0",
    ]
    openbao = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    addr_future: Future[str] = Future()
    snooper_thread = threading.Thread(target=openbao_addr_snooper)
    snooper_thread.start()

    try:
        addr = addr_future.result(timeout=10.0)
        bao = functools.partial(_bao_cmd, addr=addr, token=root_token)

        cmd = ["secrets", "enable", "-path", ENGINE_PATH, "ssh"]
        _ = bao(*cmd, json_output=False)

        _ = bao(
            "write",
            f"{ENGINE_PATH}/config/ca",
            f"private_key={ssh_ca_keys.priv}",
            f"public_key={ssh_ca_keys.pub}",
        )

        role_config = json.dumps(
            {
                "default_user": "root",
                "key_type": "ca",
                "allowed_users": f"root,{test_username}",
                "ttl": "1d",
                "max_ttl": "7d",
                "allow_user_certificates": True,
                "allow_user_key_ids": True,
                "default_extensions": {},
                "default_critical_options": {},
                "allowed_critical_options": "force-command",
            }
        )
        cmd = ["write", f"{ENGINE_PATH}/roles/{SIGNER_ROLE}", "-"]
        _ = bao(*cmd, input=role_config)

        policy_file = TESTS_DIR / "backup_signer_policy.hcl"
        _ = bao("policy", "write", policy_name, str(policy_file), json_output=False)

        _ = bao("auth", "enable", "approle", json_output=False)
        _ = bao(
            "write",
            f"auth/approle/role/{approle_name}",
            f"policies={policy_name}",
            "token_ttl=1h",
            "token_max_ttl=4h",
        )

        result = bao("read", f"auth/approle/role/{approle_name}/role-id")
        role_id = result["data"]["role_id"]

        result = bao(
            "write",
            "-f",
            f"auth/approle/role/{approle_name}/secret-id",
        )
        secret_id = result["data"]["secret_id"]

        role_id_path = tmp_path / "role_id"
        secret_id_path = tmp_path / "secret_id"
        _ = role_id_path.write_text(role_id)
        _ = secret_id_path.write_text(secret_id)

        yield config.OpenBao(
            addr=addr,
            role_id_path=role_id_path,
            secret_id_path=secret_id_path,
            auth_approle_path="approle",
            tls_cacert=None,
            tls_server_name=None,
            engine_path=ENGINE_PATH,
            signer_role=SIGNER_ROLE,
        )
    finally:
        openbao.terminate()
        try:
            _ = openbao.wait(timeout=5)
        except subprocess.TimeoutExpired:
            openbao.kill()
            _ = openbao.wait()
        snooper_thread.join()


def _bao_cmd(
    *args: str,
    addr: str,
    token: str,
    input: str | None = None,
    json_output: bool = True,
) -> dict[str, Any]:
    env = os.environ | {
        "BAO_ADDR": addr,
        "BAO_TOKEN": token,
        "BAO_FORMAT": "json",
    }
    result = subprocess.run(
        ["bao", *args],
        env=env,
        input=input,
        capture_output=True,
        text=True,
        check=True,
    )
    if json_output and result.stdout.strip():
        return json.loads(result.stdout)
    return {}


@pytest.fixture
def ssh_host_keys(tmp_path: Path) -> SSHKeyPair:
    return SSHKeyPair.generate(tmp_path, name="host")


@pytest.fixture
def ssh_config(
    openbao_ssh_ca: config.OpenBao,
    ssh_host_keys: SSHKeyPair,
) -> config.SSH:
    return config.SSH(
        ca=openbao_ssh_ca,
        public_key_path=ssh_host_keys.pub_path,
        private_key_path=ssh_host_keys.priv_path,
    )


@pytest.fixture
def ssh_ca_client(ssh_config: config.SSH) -> ssh_ca.Client:
    return ssh_ca.Client(ssh_config)


@pytest.fixture
def sshd_port(
    tmp_path: Path,
    ssh_ca_keys: SSHKeyPair,
    ssh_host_keys: SSHKeyPair,
) -> Generator[int, None, None]:
    sshd_config = tmp_path / "sshd_config"

    template_values: dict[str, str] = {
        "privateHostKeyPath": str(ssh_host_keys.priv_path),
        "authorizedKeysPath": str(),
        "trustedUserCAKeysPath": str(ssh_ca_keys.pub_path),
    }

    eprint = functools.partial(print, file=sys.stderr)

    @contextlib.contextmanager
    def sshd() -> Generator[None, None, None]:
        # `sshd` wants to be called from its full path:
        sshd_path = shutil.which("sshd")
        assert sshd_path is not None, "Could not find `sshd` in `PATH`"
        cmd = [sshd_path, "-D", "-e", "-f", sshd_config]
        p = subprocess.Popen(cmd)
        yield
        p.terminate()
        rc = p.wait()
        eprint(f"sshd return code = {rc}")

    for _ in range(3):
        sshd_port = random.randint(1025, 2**16 - 1)
        template_values["port"] = str(sshd_port)
        sshd_config_in = Path(TESTS_DIR / "sshd_config.in")
        sshd_config_tpl = string.Template(sshd_config_in.read_text())
        assert sshd_config_tpl.is_valid()
        sshd_config_rendered = sshd_config_tpl.substitute(template_values)
        assert sshd_config.write_text(sshd_config_rendered) > 0
        with sshd():
            for _ in range(3):
                try:
                    s = socket.create_connection(("127.0.0.1",  sshd_port))
                    break
                except OSError as ex:
                    if ex.errno != errno.ECONNREFUSED:
                        addr = f"127.0.0.1:{sshd_port}"
                        eprint(f"Connection refused for sshd at {addr}")
                        raise
                    time.sleep(0.05)  # give some time to sshd to start
            else:
                eprint("couldn't connect to sshd, trying another port")
                continue
            try:
                s.settimeout(0.05)
                if not s.recv(256).startswith(b"SSH-2.0-OpenSSH"):
                    eprint("invalid ssh banner, trying another port")
                    continue
            except TimeoutError:
                eprint("couldn't get ssh banner, trying another port")
                continue
            finally:
                s.close()

            yield sshd_port
            return

    # This is either unlucky or something else is up:
    pytest.fail("Could not start `sshd` after trying 3 random ports")
