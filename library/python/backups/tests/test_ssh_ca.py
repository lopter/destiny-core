import subprocess

from clan_destiny.backups import config, ssh_ca


def test_issue_certificate(ssh_config: config.SSH) -> None:
    client = ssh_ca.Client(ssh_config)
    key_id = "test-certificate-id"
    command = ["rsync", "--server", "--sender", "/data"]

    with client.issue_cert(key_id, command) as cert_path:
        result = subprocess.run(
            ["ssh-keygen", "-L", "-f", str(cert_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        cert_info = result.stdout

        assert f'Key ID: "{key_id}"' in cert_info
        assert "Type: ssh-ed25519-cert-v01@openssh.com user certificate" in cert_info
        assert "Principals:" in cert_info and "root" in cert_info
        assert "force-command rsync --server --sender /data" in cert_info
