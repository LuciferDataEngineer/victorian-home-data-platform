import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


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
            endpoint_url=endpoint_url,
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
                target = local_root / item["Key"]
                target.parent.mkdir(parents=True, exist_ok=True)
                self.client.download_file(self.bucket, item["Key"], str(target))
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
