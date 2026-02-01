import hashlib
import logging
import os

from pathlib import Path
from typing import NamedTuple

import boto3

logger = logging.getLogger("s3")


class Config(NamedTuple):
    access_key: str
    secret_key: str
    host_base: str

    def get_client(self):
        """Create a boto3 S3 client configured for this endpoint."""
        endpoint_url = f"https://{self.host_base}"
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )


def sync(
    config: Config,
    local_dir: Path,
    bucket: str,
    remote_dir: str,
    dry_run: bool,
) -> None:
    """Sync a local directory to S3.

    Uses content-based comparison (MD5/ETag) to skip unchanged files.
    Deletes remote files not present locally.
    """
    dest = os.path.join(bucket, remote_dir)
    logger.info(f"Syncing {local_dir} to {dest}")

    client = config.get_client()

    # Build dict of local files: {relative_path: local_path}
    # The local_dir name is included in the remote path (s3cmd behavior)
    local_files: dict[Path, Path] = {}
    for root, _dirs, files in os.walk(local_dir):
        for filename in files:
            filepath = Path(root) / filename
            rel_path = filepath.relative_to(local_dir.parent)
            local_files[rel_path] = filepath

    # Compute the remote prefix for key construction
    # remote_dir may be empty, in which case files go to bucket/local_dir.name/…
    prefix = f"{remote_dir.rstrip("/")}/" if remote_dir else ""

    # The listing prefix must include local_dir.name to scope correctly
    list_prefix = f"{prefix}{local_dir.name}/"

    # Get existing remote objects with their ETags
    remote_objects: dict[str, str] = {}  # key -> etag (without quotes)
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=list_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            etag = obj["ETag"].strip('"')
            remote_objects[key] = etag

    # Upload new/modified files
    for rel_path, local_path in local_files.items():
        remote_key = f"{prefix}{rel_path}" if prefix else rel_path.as_posix()
        dest = f"s3://{bucket}/{remote_key}"
        if remote_key in remote_objects:
            remote_etag = remote_objects[remote_key]
            local_md5 = _compute_md5(local_path)
            if local_md5 == remote_etag:
                logger.debug(f"Skipping unchanged: {remote_key}")
                continue
            if dry_run:
                logger.info(f"Would upload modified: {local_path} -> {dest}")
            else:
                logger.info(f"Uploading modified: {local_path} -> {dest}")
                client.upload_file(str(local_path), bucket, remote_key)
        else:
            if dry_run:
                logger.info(f"Would upload new: {local_path} -> {dest}")
            else:
                logger.info(f"Uploading new: {local_path} -> {dest}")
                client.upload_file(str(local_path), bucket, remote_key)

    # Delete removed files
    local_keys = {
        f"{prefix}{rel_path}" if prefix else rel_path.as_posix()
        for rel_path in local_files
    }
    for remote_key in remote_objects:
        if remote_key not in local_keys:
            dest = f"s3://{bucket}/{remote_key}"
            if dry_run:
                logger.info(f"Would delete removed: {dest}")
            else:
                logger.info(f"Deleting removed: {dest}")
                client.delete_object(Bucket=bucket, Key=remote_key)


def _compute_md5(file_path: Path) -> str:
    """Compute MD5 hash of a file, returning hex digest."""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def delete(
    config: Config,
    bucket: str,
    remote_path: str,
    dry_run: bool,
) -> None:
    """Recursively delete all objects under the given path."""
    dest = f"s3://{bucket}/{remote_path}"
    logger.info(f"Deleting {dest}")

    client = config.get_client()

    # Normalize prefix
    prefix = remote_path.rstrip("/")
    if prefix:
        prefix += "/"

    # List all objects with the given prefix
    paginator = client.get_paginator("list_objects_v2")
    objects_to_delete = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects_to_delete.append({"Key": obj["Key"]})

    if not objects_to_delete:
        logger.info(f"No objects found under {dest}")
        return

    if dry_run:
        for obj in objects_to_delete:
            logger.info(f"Would delete: s3://{bucket}/{obj['Key']}")
        return

    batch_size = 100
    for i in range(0, len(objects_to_delete), batch_size):
        batch = objects_to_delete[i:i + batch_size]
        response = client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": batch, "Quiet": True}
        )
        if errors := response.get("Errors"):
            for error in errors:
                logger.error(
                    f"Failed to delete {error['Key']}: "
                    f"{error['Code']} - {error['Message']}"
                )
