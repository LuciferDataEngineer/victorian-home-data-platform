import hashlib
import json
from pathlib import Path
from uuid import uuid4

from home_data.models import BronzeManifest, SourcePayload


class LocalMedallionStore:
    """Filesystem implementation of medallion storage contracts."""

    def __init__(self, data_root: Path):
        self.data_root = data_root

    def initialise(self) -> None:
        for layer in ("bronze", "silver", "gold", "quarantine"):
            (self.data_root / layer).mkdir(parents=True, exist_ok=True)

    def land_bronze(self, payload: SourcePayload) -> BronzeManifest:
        run_id = str(uuid4())
        digest = hashlib.sha256(payload.content).hexdigest()
        suffix = self._suffix(payload.media_type)
        base = (
            self.data_root
            / "bronze"
            / payload.source
            / payload.entity
            / f"extract_date={payload.publication_date}"
            / f"run_id={run_id}"
        )
        base.mkdir(parents=True, exist_ok=False)
        object_path = base / f"payload{suffix}"
        object_path.write_bytes(payload.content)
        manifest = BronzeManifest(
            run_id=run_id,
            source=payload.source,
            domain=payload.domain,
            entity=payload.entity,
            source_url=payload.source_url,
            media_type=payload.media_type,
            observation_date=payload.observation_date,
            publication_date=payload.publication_date,
            licence=payload.licence,
            sha256=digest,
            bytes=len(payload.content),
            object_path=str(object_path),
        )
        (base / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        return manifest

    @staticmethod
    def _suffix(media_type: str) -> str:
        return {
            "text/csv": ".csv",
            "application/json": ".json",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        }.get(media_type, ".bin")
