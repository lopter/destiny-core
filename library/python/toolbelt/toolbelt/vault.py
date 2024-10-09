import click
import functools
import json
import logging
import os
import pexpect
import subprocess
import sys
import tempfile

from pathlib import Path
from typing import Any, Optional

from . import sops
from .main import main


@main.group(help="Hashicorp's Vault ops")
def vault() -> None:
    pass


@vault.command(
    name="rotate-ca-cert",
    help="""Upsert a CA cert for vault into the secrets directory.

The CA is created using cfssl, the following keys are set in their respective
sops files:

- vaultTLSCACert in secrets/global.yaml
- vaultTLSCAKey in secrets/vault.yaml
- vaultTLSCACSR in secrets/vault.yaml

Because sops cannot set multiple values in a single operation you may be
prompted for credentials three times.

Note that Vault can take a certificate chain in its `tls_cert_file` listener
setting.
""",
)
@click.option("--common-name", required=True)
@click.option("--country", default=None, show_default=True)
@click.option("--location", default=None, show_default=True)
@click.option("--organization", default=None, show_default=True)
@click.option("--state", default=None, show_default=True)
@click.option("--organizational-unit", default=None, show_default=True)
@click.option(
    "--expiry",
    help="How long this certificate will be valid for (defaults to 100 years)",
    default=f"{24 * 365 * 100}h",
    show_default=True,
    required=True,
)
@click.option("--algo", default="ed25519", show_default=True, required=True)
def rotate_ca_cert(
    common_name: str,
    country: Optional[str],
    location: Optional[str],
    organization: Optional[str],
    state: Optional[str],
    organizational_unit: Optional[str],
    expiry: str,
    algo: str,
) -> None:
    if not Path(".sops.yaml").is_file():
        logging.error(
            "Sops config (`.sops.yaml`) not found.\n\nThis tool is meant "
            "to be called from the root of your config repository."
        )
        sys.exit(1)

    def clean_attrs(d):
        return {k: v for k, v in d.items() if v is not None}
    csr: dict[str, Any] = {
        "CN": common_name,
        "names": [
            clean_attrs({
                "C":  country,
                "L":  location,
                "O":  organization,
                "OU": organizational_unit,
                "ST": state,
            }),
        ],
        "key": {
            "algo": algo,
        },
        "ca": {
            "expiry": expiry
        },
    }

    logging.info("Calling cfssl to generate a CA")
    genkey = subprocess.run(
        ["cfssl", "genkey", "-initca=true", "-"],
        check=True,
        input=json.dumps(csr),
        encoding="utf-8",
        capture_output=True,
    )
    ca = json.loads(genkey.stdout)

    items = [sops.KVPair("vaultTLSCACert", ca["cert"])]
    sops.upsert(Path("secrets/global.yaml"), items)

    items = (
        sops.KVPair("vaultTLSCACSR", ca["csr"]),
        # TODO: insert that into pass instead:
        sops.KVPair("vaultTLSCAKey", ca["key"]),
    )
    sops.upsert(Path("secrets/vault.yaml"), items)

    logging.info(
        "Successfully rotated Vault CA Cert, "
        "please call vault `vault_rotate_server_cert` next"
    )


@vault.command(
    name="rotate-server-cert",
    help="""Upsert a server cert into the `secrets/vault.yaml` SOPS file.

The Vault CA saved in `secrets/global.yaml` is used to issue the server
certificate.

This (entirely) rewrites `secrets/vault.yaml` with the following key:

- vaultTLSCert
- vaultTLSKey
- vaultTLSCSR

Note that Vault can take a certificate chain in its `tls_cert_file` listener
setting.
""",
)
@click.option("--common-name", required=True)
@click.option("--country", default=None, show_default=True)
@click.option("--location", default=None, show_default=True)
@click.option("--organization", default=None, show_default=True)
@click.option("--state", default=None, show_default=True)
@click.option("--organizational-unit", default=None, show_default=True)
@click.option(
    "--expiry",
    help="How long this certificate will be valid for (defaults to 100 years)",
    default=f"{24 * 365 * 100}h",
    show_default=True,
    required=True,
)
@click.option("--algo", default="ed25519", show_default=True, required=True)
def rotate_server_cert(
    common_name: str,
    country: Optional[str],
    location: Optional[str],
    organization: Optional[str],
    state: Optional[str],
    organizational_unit: Optional[str],
    expiry: str,
    algo: str,
) -> None:
    if not Path(".sops.yaml").is_file():
        logging.error(
            "Sops config (`.sops.yaml`) not found.\n\nThis tool is meant "
            "to be called from the root of your config repository."
        )
        sys.exit(1)

    ca_cert = sops.get(Path("secrets/global.yaml"), "vaultTLSCACert")
    ca_key = sops.get(Path("secrets/vault.yaml"), "vaultTLSCAKey")

    cert_profile_name = "vault-server"
    cfssl_config = {
        "signing": {
            "default": {"expiry": expiry},
            "profiles": {
                cert_profile_name: {
                    "expiry": expiry,
                    "usages": [
                        "digital signature",
                        "key encipherment",
                        "server auth",
                    ]
                },
            }
        }
    }

    def clean_attrs(d):
        return {k: v for k, v in d.items() if v is not None}
    csr: dict[str, Any] = {
        "CN": common_name,
        "hosts": [
            common_name,
        ],
        "names": [
            clean_attrs({
                "C":  country,
                "L":  location,
                "O":  organization,
                "OU": organizational_unit,
                "ST": state,
            }),
        ],
        "key": {
            "algo": algo,
            # for reference:
            # "algo": "ecdsa", "size": 384
        },
    }

    tmp_dir = tempfile.TemporaryDirectory(suffix="multilab-toolbelt")
    with tmp_dir:
        tmp_path = Path(tmp_dir.name)

        ca_path = tmp_path / "cert.pem"
        ca_path.write_text(ca_cert, encoding="utf-8")

        ca_key_path = tmp_path / "key.pem"
        ca_key_path.write_text(ca_key, encoding="utf-8")

        cfssl_config_path = tmp_path / "config.json"
        with cfssl_config_path.open("w") as fp:
            json.dump(cfssl_config, fp)

        logging.info(f"Calling cfssl to issue a certificate for {common_name}")
        gencert = subprocess.run(
            [
                "cfssl",
                "gencert",
                "-ca", str(ca_path),
                "-ca-key", str(ca_key_path),
                "-config", cfssl_config_path,
                "-profile", cert_profile_name,
                "-",
            ],
            check=True,
            input=json.dumps(csr),
            encoding="utf-8",
            capture_output=True,
        )
        cert = json.loads(gencert.stdout)

    items = (
        sops.KVPair("vaultTLSCert", cert["cert"]),
        sops.KVPair("vaultTLSCSR", cert["csr"]),
        sops.KVPair("vaultTLSKey", cert["key"]),
    )
    sops.upsert(Path("secrets/vault.yaml"), items)


@vault.command(
    name="init",
    help="""Execute vault operator init, unseal vault, and enable KV v2.

This will upsert the secrets `root_token` and `unseal_key` under the given pass
prefix.
""",
)
@click.option(
    "--pass-prefix",
    default="io/lightsd/pki/vault/",
    required=True,
    show_default=True,
)
def init(pass_prefix: str) -> None:
    cmd = ["vault", "operator", "init", "-status"] 
    logging.info(
        f"Calling `{', '.join(cmd)}' to check if vault is already initialized."
    )
    vault_init = subprocess.run(cmd)
    if vault_init.returncode == 0:
        logging.error("Vault is already initialized")
        sys.exit(1)
    if vault_init.returncode == 1:
        logging.error("Vault returned an error:")
        logging.error(vault_init.stdout)
        sys.exit(1)
    assert vault_init.returncode == 2

    vault_init = subprocess.run(
        [
            "vault", "operator", "init",
            "-format=json",
            "-key-shares=1",
            "-key-threshold=1",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    secrets = json.loads(vault_init.stdout)
    unseal_key = secrets["unseal_keys_b64"][0]
    root_token = secrets["root_token"]

    for name, secret in (
        ("unseal_key", unseal_key),
        ("root_token", root_token),
    ):
        dest = f"{pass_prefix}{name}"
        logging.info(f"Save the {name} in pass with name {dest}")
        subprocess.run(
            ["pass", "insert", "--force", "--multiline", dest],
            input=secret,
            check=True,
            encoding="ascii",
        )

    _unseal(unseal_key)

    logging.info("Enabling the KV v2 secrets engine at kv/")
    vault_env = os.environ.copy()
    vault_env["VAULT_TOKEN"] = root_token
    cmd = ["vault", "secrets", "enable", "-version=2", "kv"]
    subprocess.run(cmd, env=vault_env, check=True)


@vault.command(
    name="unseal",
    help="Unseal vault using a key stored in pass",
)
@click.option(
    "--pass-prefix",
    default="io/lightsd/pki/vault/",
    required=True,
    show_default=True,
)
def unseal(pass_prefix: str) -> None:
    unseal_key_path = f"{pass_prefix}unseal_key"
    logging.info(f"Waiting for `pass show {unseal_key_path}`")
    unseal_key = subprocess.run(
        ["pass", "show", unseal_key_path],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout
    _unseal(unseal_key)


def _unseal(unseal_key: str) -> None:
    logging.info("Unsealing vault")
    vault = pexpect.spawn("vault operator unseal")
    vault.expect("Unseal Key")
    vault.sendline(unseal_key)
    vault.wait()
    vault.close()
    if vault.exitstatus != 0:
        logging.error(
            f"vault operator unseal failed with "
            f"status {vault.status}"
        )
        sys.exit(1)


@vault.command(
    name="rotate-approle",
    help="""Replace the given AppRole credentials.

The following secrets will be written to the given secrets file.
""",
)
@click.option(
    "--secrets-file-path",
    help="Path to the file where sops will set secrets",
    default=Path("secrets/global.yaml"),
    show_default=True,
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
)
@click.option(
    "--secrets-prefix",
    help="The name of the sops secret corresponding to this AppRole.",
    required=True,
)
@click.option(
    "--vault-policy-path",
    help=(
        "Path to the Vault policy for this role defaults to "
        "../multilab/library/vault-policies/<ROLE>.hcl"
    ),
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--vault-root-token-pass-name",
    help="The name of the `pass' secret where your Vault root token is stored",
    default="io/lightsd/pki/vault/root_token",
    show_default=True,
)
@click.option("--role", help="AppRole name to rotate", required=True)
def rotate_approle(
    role: str,
    vault_root_token_pass_name: str,
    vault_policy_path: Optional[Path],
    secrets_prefix: str,
    secrets_file_path: Path,
) -> None:
    if vault_policy_path is None:
        vault_policy_path = Path("../multilab/library/vault-policies", f"{role}.hcl")

    # Take the policies as some kind of Nix dependency like
    # filegroup in Bazel and then find a way to reference
    # the filegroup from Python to dereference its paths.
    sops_config_path = Path(".sops.yaml")
    for desc, path in (
        ("sops config file", sops_config_path),
        (f"vault policy file for {role}", vault_policy_path),
    ):
        if path.is_file():
            continue
        logging.error(
                f"Could not find {desc} ({path}).\n\nThis tool is meant "
                f"to be called from the root of your config repository"
            )
        sys.exit(1)

    logging.info("Fetching vault root token out of pass")
    vault_token = subprocess.run(
        ["pass", "show", vault_root_token_pass_name],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout

    vault_env = os.environ.copy()
    vault_env["VAULT_TOKEN"] = vault_token
    vault_call = functools.partial(
        subprocess.run,
        check=True,
        env=vault_env,
        encoding="utf-8",
    )

    vault_policy_name = role
    vault_approle_path = f"auth/approle/role/{role}"

    auth_methods = json.loads(vault_call(
        ["vault", "auth", "list", "-format=json"],
        capture_output=True,
    ).stdout)
    if "approle/" not in auth_methods:
        logging.info("Enabling the approle auth method at approle/")
        vault_call(["vault", "auth", "enable", "approle"])

    logging.info(f"Making vault calls to create AppRole {role}")

    vault_call([
        "vault", "write", vault_approle_path,
        f"token_policies={vault_policy_name}",
        "token_ttl=1h",
        "token_max_ttl=4h",
    ])

    cmd = ["vault", "read", "-format=json", f"{vault_approle_path}/role-id"]
    create_role_id = vault_call( cmd, capture_output=True)
    role_id = json.loads(create_role_id.stdout)["data"]["role_id"]

    cmd = ["vault", "write", "-force", "-format=json", f"{vault_approle_path}/secret-id"]
    create_secret_id = vault_call(cmd, capture_output=True)
    secret_id = json.loads(create_secret_id.stdout)["data"]["secret_id"]

    items = (
        sops.KVPair(f"{secrets_prefix}RoleId", role_id),
        sops.KVPair(f"{secrets_prefix}SecretId", secret_id),
    )
    sops.upsert(secrets_file_path, items)

    logging.info(f"Calling vault policy to create policy {vault_policy_name}")
    cmd = ["vault", "policy", "write", vault_policy_name, vault_policy_path]
    vault_call(cmd)

    logging.info("All done")
