import click
import itertools
import json
import logging
import ovh
import sys
import yaml

from collections.abc import Generator
from typing import Any, Final, cast

from . import pass_store

PASS_NAME: Final[str] = "com/ovh/pentosaurus@gmail.com"
ZONE_NAME: Final[str] = "atelierpentosaurus.com"

ZONE_RECORDS_ENDPOINT: Final[str] = f"/domain/zone/{ZONE_NAME}/record"

TTL: Final[int] = 60 * 15

OVHRecord = dict[str, Any]

# We could have an OVH sub-command on which to set this common option but this
# will do for now to keep things somewhat DRY:
pass_name_option = click.option(
    "--pass-name",
    default=PASS_NAME,
    required=True,
    show_default=True,
    help="Name of the password in pass with the OVH credentials",
)


@click.group(
    help=(
        f"Tools for managing Pentosaurus' web landing page at "
        f"https://www.{ZONE_NAME}/"
    ),
)
def pentosaurus() -> None:
    pass


@pentosaurus.command(
    name="dns-list",
    help=f"List DNS records for {ZONE_NAME}.",
)
@pass_name_option
def dns_list(pass_name: str) -> None:
    ovh_client = new_ovh_client(pass_name)
    records = list_zone(ovh_client, ZONE_NAME)
    json.dump(list(records), sys.stdout, indent=2, sort_keys=True)


@pentosaurus.command(
    name="dns-cleanup",
    help=f"Delete all DNS records for {ZONE_NAME} except NS records.",
)
@pass_name_option
def dns_cleanup(pass_name: str) -> None:
    ovh_client = new_ovh_client(pass_name)
    prompt = f"Confirm deletion of all records except NS ones in {ZONE_NAME}"
    if not click.confirm(prompt):
        return
    for record in list_zone(ovh_client, ZONE_NAME):
        record_type = record["fieldType"]
        if record_type == "NS":
            continue
        record_id = record["id"]
        logging.info(f"Deleting {record_type} record {record_id}")
        ovh_client.delete(f"{ZONE_RECORDS_ENDPOINT}/{record_id}")


def list_zone(client: ovh.Client, zone_name: str) -> Generator[OVHRecord]:
    record_ids: list[int] = cast(list[int], client.get(ZONE_RECORDS_ENDPOINT))
    for num, id in enumerate(record_ids, start=1):
        count = f"{num}/{len(record_ids)}"
        logging.info(f"Fetching details for record {count} in {zone_name}…")
        yield cast(OVHRecord, client.get(f"{ZONE_RECORDS_ENDPOINT}/{id}"))


@pentosaurus.command(
    name="dns-set",
    help=f"""Point www.{ZONE_NAME} and {ZONE_NAME} to the given IP addresses.

This uses the OVH API, which needs the following credentials:

- application_key;
- application_secret;
- consumer_key.

This command expects the credentials to be stored
in a `certbot_api_keys` YAML object in a [pass] file.

[pass]: https://www.passwordstore.org/.
"""
)
@pass_name_option
@click.option("--a", required=True)
@click.option("--aaaa", required=True)
def dns_set(pass_name: str, a: str, aaaa: str) -> None:
    ovh_client = new_ovh_client(pass_name)

    to_update = []
    existing = set()
    logging.info("Checking existing records…")
    for record in list_zone(ovh_client, ZONE_NAME):
        name = record["subDomain"]
        if name != "" and name != "www":
            continue
        if record["fieldType"] == "A" and record["target"] != a:
            to_update.append({
                "id": record["id"],
                "fieldType": "A",
                "subDomain": name,
                "target": a,
                "ttl": TTL,
            })
            existing.add(("A", name))
        elif record["fieldType"] == "AAAA" and record["target"] != aaaa:
            to_update.append({
                "id": record["id"],
                "fieldType": "AAAA",
                "subDomain": name,
                "target": aaaa,
                "ttl": TTL,
            })
            existing.add(("AAAA", name))

    to_create = []
    missing = set(itertools.product(("A", "AAAA"), ("", "www"))) - existing
    for record in missing:
        field_type, target = record
        to_create.append({
            "fieldType": field_type,
            "subDomain": target,
            "target": a if field_type == "A" else aaaa,
            "ttl": TTL,
        })

    for record in to_update:
        logging.info(
            f"Updating record {record['subDomain'] or '@'} "
            f"{record['fieldType']} {record['target']}"
        )
        record_id = record.pop("id")
        ovh_client.put(f"/domain/zone/{ZONE_NAME}/record/{record_id}", **record)

    for record in to_create:
        logging.info(
            f"Creating record {record['subDomain'] or '@'} "
            f"{record['fieldType']} {record['target']}"
        )
        ovh_client.post(f"/domain/zone/{ZONE_NAME}/record", **record)


def new_ovh_client(pass_name: str) -> ovh.Client:
    pass_contents = pass_store.show(pass_name)
    credentials = yaml.safe_load(pass_contents)["certbot_api_keys"]
    return ovh.Client(endpoint="ovh-eu", **credentials)
