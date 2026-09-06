import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def sync_blob_prefix_down(account_url: str, container: str, local_root: Path) -> None:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient(account_url, credential=DefaultAzureCredential())
    client = service.get_container_client(container)
    local_root.mkdir(parents=True, exist_ok=True)
    for blob in client.list_blobs():
        target = local_root / blob.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(client.download_blob(blob.name).readall())
    LOGGER.info("Cloud data synchronised down", extra={"stage": "cloud_sync"})


def sync_blob_prefix_up(account_url: str, container: str, local_root: Path) -> None:
    from azure.core.exceptions import ResourceExistsError
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient(account_url, credential=DefaultAzureCredential())
    client = service.get_container_client(container)
    try:
        client.create_container()
    except ResourceExistsError:
        pass
    for path in local_root.rglob("*"):
        if path.is_file():
            client.upload_blob(path.relative_to(local_root).as_posix(), path.read_bytes(), overwrite=True)
    LOGGER.info("Cloud data synchronised up", extra={"stage": "cloud_sync"})
