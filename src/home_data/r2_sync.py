import logging
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

LOGGER = logging.getLogger(__name__)


def normalise_r2_endpoint(endpoint_url: str, bucket: str) -> str:
    """Accept Cloudflare's account endpoint or a copied bucket-qualified endpoint."""
    parsed = urlsplit(endpoint_url.strip())
    path = parsed.path.rstrip("/")
    if path == f"/{bucket}":
        path = ""
    elif path:
        raise ValueError("R2 endpoint must not contain a path other than the configured bucket")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class R2MedallionSync:
    """Synchronise medallion files through Cloudflare's S3-compatible R2 API."""

    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
    ):
        import boto3

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=normalise_r2_endpoint(endpoint_url, bucket),
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def download(self, local_root: Path) -> int:
        local_root.mkdir(parents=True, exist_ok=True)
        count = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket):
            for item in page.get("Contents", []):
                key = item["Key"]
                # The R2 dashboard represents folders as zero-byte objects. They
                # are display markers, not pipeline inputs, and downloading one
                # as a file would block creation of its child directory.
                if key.endswith("/"):
                    continue
                target = local_root / key
                target.parent.mkdir(parents=True, exist_ok=True)
                self.client.download_file(self.bucket, key, str(target))
                count += 1
        LOGGER.info("R2 synchronised down", extra={"stage": "cloud_sync", "rows": count})
        return count

    def upload(self, local_root: Path) -> int:
        count = 0
        for path in local_root.rglob("*"):
            if path.is_file():
                self.client.upload_file(
                    str(path), self.bucket, path.relative_to(local_root).as_posix()
                )
                count += 1
        LOGGER.info("R2 synchronised up", extra={"stage": "cloud_sync", "rows": count})
        return count
