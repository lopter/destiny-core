import pytest
import socket

from pathlib import Path

from clan_destiny.backups import config, ssh_ca


@pytest.fixture
def test_config(tmp_path: Path, ssh_config: config.SSH) -> Path:
    cfg = config.Config(
        jobs_by_name={
            "test_job": config.BackupJob(
                type=config.BackupType.RSYNC,
                direction=config.BackupDirection.PUSH,
                local_host=socket.getfqdn(),
                local_path="/var/empty",
                remote_host="nsrv-sfo-ashpool.kalessin.fr",
                remote_path="/stash/backups/empty",
                one_file_system=True,
                password_path=None,
                retention=None,
            ),
        },
        restic=None,
        ssh=ssh_config,
    )
    test_config = tmp_path / "test_config.json"
    with test_config.open("w") as fp:
        assert fp.write(cfg.model_dump_json()) > 0
    return test_config


def test_sshd_agent(
    sshd_port: int,
    ssh_ca_client: ssh_ca.Client,
    ssh_config: config.SSH,
    test_username: str,
    test_config: Path,
) -> None:
    cli_path = Path(__file__).parent.parent / "bin/clan-destiny-backups"
    print(f"host_public_key={ssh_config.public_key.read_text()}")
    with ssh_ca_client.issue_cert(
        id="test",
        command=[str(cli_path), "-c", str(test_config), "sshd-agent"],
        valid_principals=[test_username],
    ) as cert:
        import shlex
        print(shlex.join([
            "ssh-untrusted",
            "-i", str(ssh_config.private_key_path),
            "-i", str(cert),
            "-p", str(sshd_port),
            "-o", "SendEnv=PYTHONPATH",
            f"{test_username}@localhost",
        ]))
