import functools
import json
import os
import pytest
import re
import subprocess
import sys
import tempfile
import threading

from collections.abc import Generator
from concurrent.futures import Future
from pathlib import Path
from typing import Any, NamedTuple

from clan_destiny.backups import config


TESTS_DIR = Path(__file__).parent
ENGINE_PATH = "ssh-backups-ca"
SIGNER_ROLE = "backups-dump"


class KeyPair(NamedTuple):
    public_key: Path
    private_key: Path


_LISTENER_PATTERN = re.compile(
    r"core\.cluster-listener\.tcp: starting listener: listener_address=([^:]+):(\d+)"
)


@pytest.fixture
def openbao_ssh_ca() -> Generator[config.OpenBao, None, None]:
    root_token = "root-token"
    approle_name = "backup-client"
    policy_name = "backup-ssh-signer"

    def openbao_addr_snooper() -> None:
        assert openbao.stderr is not None
        for line in openbao.stderr:
            sys.stderr.write(line)
            sys.stderr.flush()
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
        bao(*cmd, json_output=False)

        with tempfile.TemporaryDirectory(prefix="openbao-test-") as tmp_dir:
            tmp_path = Path(tmp_dir)

            ca_key = tmp_path / "ssh-ca"
            ca_pub = tmp_path / "ssh-ca.pub"
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "ed25519",
                    "-C",
                    "Test Backups SSH CA",
                    "-N",
                    "",
                    "-f",
                    str(ca_key),
                ],
                check=True,
                capture_output=True,
            )

            bao(
                "write",
                f"{ENGINE_PATH}/config/ca",
                f"private_key={ca_key.read_text()}",
                f"public_key={ca_pub.read_text()}",
            )

            role_config = json.dumps(
                {
                    "default_user": "root",
                    "key_type": "ca",
                    "allowed_users": "root",
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
            bao(*cmd, input=role_config)

            policy_file = TESTS_DIR / "backup_signer_policy.hcl"
            bao("policy", "write", policy_name, str(policy_file), json_output=False)

            bao("auth", "enable", "approle", json_output=False)
            bao(
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
            role_id_path.write_text(role_id)
            secret_id_path.write_text(secret_id)

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
def ssh_identity() -> Generator[KeyPair, None, None]:
    with tempfile.TemporaryDirectory(
        prefix="test-backups",
        ignore_cleanup_errors=True,
    ) as tmp_dir:
        private_key = Path(tmp_dir) / "id_ed25519"
        public_key = private_key.with_suffix(".pub")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(private_key)],
            check=True,
            capture_output=True,
        )
        yield KeyPair(public_key, private_key)


@pytest.fixture
def ssh_config(
    openbao_ssh_ca: config.OpenBao,
    ssh_identity: KeyPair,
) -> config.SSH:
    return config.SSH(
        ca=openbao_ssh_ca,
        public_key=ssh_identity.public_key,
        private_key=ssh_identity.private_key,
    )
