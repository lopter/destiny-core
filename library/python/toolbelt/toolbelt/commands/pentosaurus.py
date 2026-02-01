import click
import errno
import itertools
import json
import logging
import multiprocessing
import os
import ovh
import PIL.Image
import shutil
import sys
import yaml

from collections.abc import Generator, Iterator
from pathlib import Path
from typing import Any, Final, cast, NamedTuple

from . import utils

logger = logging.getLogger("pentosaurus")

ZONE_NAME: Final[str] = "atelierpentosaurus.com"

ZONE_RECORDS_ENDPOINT: Final[str] = f"/domain/zone/{ZONE_NAME}/record"

TTL: Final[int] = 60 * 15

OVHRecord = dict[str, Any]

# Maybe we could also have an utility to create some kind of utility to DRY
# the OVH related code when if we need to manage another website the same way
# as pentosaurus.
pass_name_option = utils.pass_store.pass_name_option(
    default="com/ovh/pentosaurus@gmail.com",
    help="Name of the password in pass with the OVH credentials",
)


@click.group(
    help=f"Manage Pentosaurus' web landing page at https://www.{ZONE_NAME}/",
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
    pass_contents = utils.pass_store.show(pass_name)
    credentials = yaml.safe_load(pass_contents)["certbot_api_keys"]
    return ovh.Client(endpoint="ovh-eu", **credentials)


@click.group(help="Manage pictures for Pentosaurus")
def photos() -> None:
    pass


pentosaurus.add_command(photos)


@photos.command(
    help="Process a directory of photos so that we can use them in the website."
)
@click.option(
    "--input-dir",
    help="Directory containing the pictures to process",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--output-dir",
    help="Directory where the processed pictures will be stored",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--thumbnail-size",
    help="Size used to create square thumbnails of the images",
    required=True,
    type=click.IntRange(min=1),
    default=200,
    show_default=True,
)
def convert(
    input_dir: Path,
    output_dir: Path,
    thumbnail_size: int,
) -> None:
    output_dir.mkdir(exist_ok=True)

    def jobs() -> Iterator[tuple[Path, int, Path]]:
        for filename in input_dir.iterdir():
            yield (output_dir, thumbnail_size, input_dir / filename)

    with multiprocessing.Pool() as workers:
        result = workers.starmap_async(process_image, jobs())
        images = [entry.asdict() for entry in result.get()]
    workers.join()

    manifest = {"version": 1, "images": images}
    with (output_dir / "manifest.json").open("w") as fp:
        json.dump(manifest, fp, indent=2)


class ManifestEntry(NamedTuple):
    name: str
    width: int
    height: int

    def asdict(self) -> dict[str, Any]:
        return self._asdict()


def process_image(output_dir: Path, thumbnail_size: int, image_path: Path) -> ManifestEntry:
    with PIL.Image.open(image_path) as source:
        width, height = source.size
        mid_x, mid_y = (width // 2, height // 2)
        half_size = source.resize((mid_x, mid_y))
        # To get the thumbnail, fit a square at the middle of the image,
        # then crop it out, and resize it to the thumbnail size:
        half_square_size = min(width, height) // 2
        upper_left = (mid_x - half_square_size, mid_y - half_square_size)
        lower_right = (mid_x + half_square_size, mid_y + half_square_size)
        thumbnail = source.crop(box=(*upper_left, *lower_right))
        thumbnail = thumbnail.resize((thumbnail_size, thumbnail_size))
        opts = {}
        if source.format == "JPEG":
            opts.update(quality=90, optimize=True)
        else:
            msg = f"No saving options defined for image format {source.format}"
            logger.info(msg)

    image_dir = output_dir / image_path.stem
    image_dir.mkdir(exist_ok=True)
    full_size_path = image_dir / f"full{image_path.suffix}"
    full_size_path.unlink(missing_ok=True)
    try:
        full_size_path.hardlink_to(image_path)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise exc
        shutil.copy2(image_path, full_size_path)
    thumbnail.save(image_dir / f"thumb{image_path.suffix}", **opts)
    half_size.save(image_dir / f"half{image_path.suffix}", **opts)

    return ManifestEntry(image_path.stem, width, height)


BUCKET_NAME: Final[str] = "pentosaurus-assets"
BUCKET_HOST_BASE: Final[str] = "fly.storage.tigris.dev"


s3_pass_name_option = click.option(
    "--pass-name",
    help="Name of the password in pass with the AWS-S3 compatible credentials.",
    default=f"dev/tigris/storage/fly/{BUCKET_NAME}",
    required=True,
    show_default=True,
)


@photos.command(
    help=f"Upload images to S3-compatible storage on `tigrisdata.com`",
)
@click.option(
    "--local-dir",
    required=True,
    help=(
        "Directory where the pictures processed "
        "by the `convert` command are stored"
    ),
    type=click.Path(file_okay=False, exists=True, path_type=Path),
)
@click.option(
    "--remote-dir",
    required=True,
    help="Pictures are uploaded to this directory of the bucket",
    default="photos",
    show_default=True,
)
@click.option(
    "--bucket",
    required=True,
    default=BUCKET_NAME,
    show_default=True,
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    show_default=True,
    help="Show what would be synced without actually syncing",
)
@s3_pass_name_option
@click.pass_context
def upload(
    ctx: click.Context,
    local_dir: Path,
    remote_dir: str,
    bucket: str,
    dry_run: bool,
    pass_name: str,
) -> None:
    if (s3_config := get_s3_config(pass_name)) is None:
        ctx.exit(1)

    remote_prefix, remote_basename = os.path.split(remote_dir.rstrip("/"))
    if local_dir.name != remote_basename:
        click.echo(
            "The name of the local directory must match the name of "
            "the remote directory (remote directory is actually a prefix)"
        )
        want_dir = local_dir.parent / remote_basename
        if not click.confirm(f"Rename {local_dir} to {want_dir}?"):
            click.echo("Upload cancelled", err=True)
            ctx.exit(2)
        if want_dir.exists():
            click.echo(f"{want_dir} already exists", err=True)
            click.echo("Upload cancelled", err=True)
            ctx.exit(3)
        local_dir.rename(want_dir)
        local_dir = want_dir

    utils.s3.sync(s3_config, local_dir, bucket, remote_prefix, dry_run)

    if not dry_run:
        click.echo(f"""{local_dir} has been uploaded.

Don't forget to set CORS rules on {bucket} if it has not been done:

- See: https://www.tigrisdata.com/docs/buckets/cors/#specifying-cors-rules-via-the-tigris-dashboard
- Allowed Methods: GET
- Origins: *""")


@photos.command(
    help="Recursively delete paths from the given bucket on `tigrisdata.com`",
)
@click.option(
    "--remote-path",
    help="The remote path to recursively delete",
)
@click.option(
    "--bucket",
    required=True,
    default=BUCKET_NAME,
    show_default=True,
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    show_default=True,
    help="Show what would be deleted without actually deleting",
)
@s3_pass_name_option
@click.pass_context
def delete(
    ctx: click.Context,
    remote_path: str,
    bucket: str,
    dry_run: bool,
    pass_name: str,
) -> None:
    if (s3_config := get_s3_config(pass_name)) is None:
        ctx.exit(1)

    prompt = f"Recursively delete {remote_path} from {bucket}?"
    if dry_run or click.confirm(prompt):
        utils.s3.delete(s3_config, bucket, remote_path, dry_run)


def get_s3_config(pass_name: str) -> utils.s3.Config | None:
    pass_contents = utils.pass_store.show(pass_name)
    match credentials := yaml.safe_load(pass_contents):
        case {
            "AWS_ACCESS_KEY_ID": access_key,
            "AWS_SECRET_ACCESS_KEY": secret_key,
        }:
            return utils.s3.Config(access_key, secret_key, BUCKET_HOST_BASE)
        case _:
            if not isinstance(credentials, dict):
                logger.info(f"Expected to find a dict in pass but got a {type(credentials)}")
            else:
                wanted = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
                actual = tuple(credentials.keys())
                msg = f"Expected to find {wanted} in pass, but got {actual}"
                logger.info(msg)
            return None
