import json
import logging
import re
import subprocess
import sys
import tempfile
import yaml

from pathlib import Path
from typing import Iterable, NamedTuple


class KVPair(NamedTuple):
    key: str
    value: str


def upsert(secrets_file: Path, items: Iterable[KVPair]) -> None:
    if secrets_file.exists():
        for key, value in items:
            logging.info(f"Calling sops to set {key} in {secrets_file}")
            key_path = f"[\"{key}\"]"
            json_value = f"\"{value.replace('\n', '\\n')}\""
            cmd = ["sops", "set", str(secrets_file), key_path, json_value]
            subprocess.run(cmd, check=True)
        return

    logging.info(f"Looking up sops creation rule for {secrets_file}")
    with Path(".sops.yaml").open() as fp:
        sops_config = yaml.safe_load(fp)
    encrypt_sops_config = {}
    for rule in sops_config.get("creation_rules", []):
        if re.search(rule.get("path_regex", ""), str(secrets_file)) is not None:
            rule["path_regex"] = ".*"
            encrypt_sops_config["creation_rules"] = [rule]
            break # stop at first match like sops
    else:
        logging.error(
            f"Could not find a creation rule for "
            f"{secrets_file} in your sops config"
        )
        sys.exit(1)

    with tempfile.NamedTemporaryFile(
        suffix="multilab-toolbelt"
    ) as tmp_sops_config:
        with Path(tmp_sops_config.name).open("w") as fp:
            json.dump(encrypt_sops_config, fp)
        data = dict(items)
        key_names = ", ".join(data.keys())
        logging.info(f"Saving {key_names} in {secrets_file} with sops encrypt")
        cmd = [
            "sops",
            "--verbose",
            "--indent", "2",
            "--config", tmp_sops_config.name,
            "encrypt",
            "--output", str(secrets_file),
            "--output-type", "yaml",
            "--input-type", "yaml",
            "/dev/stdin"
        ]
        subprocess.run(
            cmd,
            input=yaml.safe_dump(data),
            check=True,
            encoding="utf-8",
        )


def get(secrets_file: Path, key: str) -> str:
    logging.info(f"Calling sops to load {key} from {secrets_file}")
    return subprocess.run(
        ["sops", "decrypt", "--extract", f"[\"{key}\"]", str(secrets_file)],
        check=True,
        encoding="utf-8",
        capture_output=True,
    ).stdout
