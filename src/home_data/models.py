from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SourcePayload(BaseModel):
    source: str
    domain: str
    entity: str
    content: bytes
    media_type: str
    source_url: str
    observation_date: str
    publication_date: str
    licence: str = "CC-BY-4.0"


class BronzeManifest(BaseModel):
    run_id: str
    source: str
    domain: str
    entity: str
    source_url: str
    media_type: str
    observation_date: str
    publication_date: str
    licence: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sha256: str
    bytes: int
    object_path: str
    status: str = "landed"


class QualityResult(BaseModel):
    check_name: str
    passed: bool
    severity: str
    message: str

