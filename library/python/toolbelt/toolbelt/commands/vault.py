import click
import functools
import json
import logging
import os
import pexpect  # type: ignore
import subprocess
import sys
import tempfile

from pathlib import Path
from typing import Any, Optional

from . import utils


@click.group(help="Hashicorp's Vault ops")
def vault() -> None:
    pass


@vault.command(
    name="rotate-ca-cert",
    help="""Set a new CA cert for vault into the clan vars of the given machine.

The CA is created using cfssl, the following clan vars are set for the given
machine and vars generator:

- clan-destiny-vault-common/tlsCaCert

While the secret `tls_ca_key` is set in pass in the directory given by
`--pass-dir`.

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
@click.option(
    "--machine",
    help="The clan machine to use with `clan vars set`",
    required=True,
)
@click.option(
    "--pass-dir",
    default="io/lightsd/pki/vault",
    required=True,
    show_default=True,
)
@utils.clan.ensure_root_directory
def rotate_ca_cert(
    common_name: str,
    country: Optional[str],
    location: Optional[str],
    organization: Optional[str],
    state: Optional[str],
    organizational_unit: Optional[str],
    expiry: str,
    algo: str,
    machine: str,
    pass_dir: str,
) -> None:
    def clean_attrs(d):
        return {k: v for k, v in d.items() if v is not None}

    csr: dict[str, Any] = {
        "CN": common_name,
        "names": [
            clean_attrs(
                {
                    "C": country,
                    "L": location,
                    "O": organization,
                    "OU": organizational_unit,
                    "ST": state,
                }
            ),
        ],
        "key": {
            "algo": algo,
        },
        "ca": {"expiry": expiry},
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

    utils.clan.vars_set(machine, {"clan-destiny-vault-common/tlsCaCert": ca["cert"]})

    name = "tls_ca_key"
    dest = os.path.join(pass_dir, name)
    logging.info(f"Saving TLS CA key in pass with name {dest}")
    utils.utils.pass_store.set(dest, ca["key"])

    logging.info(
        "Successfully rotated Vault CA Cert, "
        "please call `vault rotate-server-cert` next"
    )


@vault.command(
    name="rotate-server-cert",
    help="""Set a new server cert into the clan vars of the given machine.

The given vars are set:

- clan-destiny-vault/tlsCertChain
- clan-destiny-vault/tlsKey

The TLS CA cert is read from `clan-destiny-vault-common/tlsCaCert` while the
TLS CA key is read from the secret `tls_ca_key` in the directory given by
`--pass-dir`.
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
@click.option("--machine", required=True)
@click.option(
    "--pass-dir",
    default="io/lightsd/pki/vault",
    required=True,
    show_default=True,
)
@utils.clan.ensure_root_directory
def rotate_server_cert(
    common_name: str,
    country: Optional[str],
    location: Optional[str],
    organization: Optional[str],
    state: Optional[str],
    organizational_unit: Optional[str],
    expiry: str,
    algo: str,
    machine: str,
    pass_dir: str,
) -> None:
    name = "clan-destiny-vault-common/tlsCaCert"
    ca_cert = utils.clan.vars_get(machine, [name])[name]
    ca_key = utils.pass_store.show(os.path.join(pass_dir, "tls_ca_key"))

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
                    ],
                },
            },
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
            clean_attrs(
                {
                    "C": country,
                    "L": location,
                    "O": organization,
                    "OU": organizational_unit,
                    "ST": state,
                }
            ),
        ],
        "key": {
            "algo": algo,
            # for reference:
            # "algo": "ecdsa", "size": 384
        },
    }

    tmp_dir = tempfile.TemporaryDirectory(suffix="clan-destiny-toolbelt")
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
                "-ca",
                str(ca_path),
                "-ca-key",
                str(ca_key_path),
                "-config",
                cfssl_config_path,
                "-profile",
                cert_profile_name,
                "-",
            ],
            check=True,
            input=json.dumps(csr),
            encoding="utf-8",
            capture_output=True,
        )
        cert = json.loads(gencert.stdout)

    tls_cert_chain = f"{cert['cert'].strip()}\n{ca_cert}\n"
    secrets = {
        "clan-destiny-vault/tlsKey": cert["key"],
        "clan-destiny-vault/tlsCertChain": tls_cert_chain,
    }
    utils.clan.vars_set(machine, secrets)


@vault.command(
    name="init",
    help="""Execute vault operator init, unseal vault, and enable KV v2.

This will upsert the secrets `root_token` and `unseal_key` in the given pass
directory.
""",
)
@click.option(
    "--pass-dir",
    default="io/lightsd/pki/vault",
    required=True,
    show_default=True,
)
def init(pass_dir: str) -> None:
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
            "vault",
            "operator",
            "init",
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
        utils.pass_store.set(os.path.join(pass_dir, name), secret)

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
    "--pass-dir",
    default="io/lightsd/pki/vault",
    required=True,
    show_default=True,
)
def unseal(pass_dir: str) -> None:
    _unseal(utils.pass_store.show(os.path.join(pass_dir, "unseal_key")))


def _unseal(unseal_key: str) -> None:
    logging.info("Unsealing vault")
    vault = pexpect.spawn("vault operator unseal")
    vault.expect("Unseal Key")
    vault.sendline(unseal_key)
    vault.wait()
    vault.close()
    if vault.exitstatus != 0:
        logging.error(f"vault operator unseal failed with " f"status {vault.status}")
        sys.exit(1)


@vault.command(
    name="rotate-approle",
    help="""Replace the given AppRole credentials.

The following clan vars will be set for the given machine and var generator:

- `vaultRoleId`;
- `vaultSecretId`.
""",
)
@click.option(
    "--vault-policy-path",
    help=(
        "Path to the Vault policy for this role defaults to "
        "../destiny-config/library/vault-policies/<ROLE>.hcl"
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
@click.option(
    "--machine",
    help="The clan machine to use with `clan vars set`",
    required=True,
)
@click.option(
    "--vars-generator",
    help=(
        "The name of the clan vars generator where `vaultRoleId` "
        "and `vaultSecretId` for this AppRole will be set"
    ),
    required=True,
)
@utils.clan.ensure_root_directory
def rotate_approle(
    role: str,
    vault_root_token_pass_name: str,
    vault_policy_path: Optional[Path],
    machine: str,
    vars_generator: str,
) -> None:
    # It would be nice if we could take the policies as some kind of dependency
    # for this script, like you would do with a filegroup in Bazel.
    if vault_policy_path is None:
        vault_policy_path = Path(
            "../destiny-config/library/vault-policies", f"{role}.hcl"
        )
        if not vault_policy_path.is_file():
            logging.error(f"Could not find vault policy file at {vault_policy_path}")
            sys.exit(1)

    vault_env = os.environ.copy()
    vault_env["VAULT_TOKEN"] = utils.pass_store.show(vault_root_token_pass_name)
    vault_call = functools.partial(
        subprocess.run,
        check=True,
        env=vault_env,
        encoding="utf-8",
    )

    vault_policy_name = role
    vault_approle_path = f"auth/approle/role/{role}"

    auth_methods = json.loads(
        vault_call(
            ["vault", "auth", "list", "-format=json"],
            capture_output=True,
        ).stdout
    )
    if "approle/" not in auth_methods:
        logging.info("Enabling the approle auth method at approle/")
        vault_call(["vault", "auth", "enable", "approle"])

    logging.info(f"Making vault calls to create AppRole {role}")

    vault_call(
        [
            "vault",
            "write",
            vault_approle_path,
            f"token_policies={vault_policy_name}",
            "token_ttl=1h",
            "token_max_ttl=4h",
        ]
    )

    cmd = ["vault", "read", "-format=json", f"{vault_approle_path}/role-id"]
    create_role_id = vault_call(cmd, capture_output=True)
    role_id = json.loads(create_role_id.stdout)["data"]["role_id"]

    cmd = [
        "vault",
        "write",
        "-force",
        "-format=json",
        f"{vault_approle_path}/secret-id",
    ]
    create_secret_id = vault_call(cmd, capture_output=True)
    secret_id = json.loads(create_secret_id.stdout)["data"]["secret_id"]

    vars = {
        f"{vars_generator}/vaultRoleId": role_id,
        f"{vars_generator}/vaultSecretId": secret_id,
    }
    utils.clan.vars_set(machine, vars)

    logging.info(f"Calling vault policy to create policy {vault_policy_name}")
    cmd = ["vault", "policy", "write", vault_policy_name, str(vault_policy_path)]
    vault_call(cmd)

    logging.info("All done")
