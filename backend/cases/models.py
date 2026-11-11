from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _reject_control_characters(value: str) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("control characters are not allowed")
    return value


class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return _reject_control_characters(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _reject_control_characters(value.strip())


class CaseResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    created_at: datetime
    created_by: str
    created_by_verified: Literal[False] = False


class EvidenceSummary(BaseModel):
    image: int = 0
    audio: int = 0
    video: int = 0


class CaseDetailResponse(CaseResponse):
    evidence_count: int
    evidence_by_media_type: EvidenceSummary


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    limit: int
    offset: int


class RegisterEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str | None = Field(default=None, min_length=1, max_length=100)
    filename: str = Field(min_length=1, max_length=500)
    media_type: Literal["image", "audio", "video"]
    role: Literal["Evidence", "Reference", "Control"]
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("evidence_id", "filename")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return _reject_control_characters(value)


class EvidenceResponse(BaseModel):
    case_id: str
    evidence_id: str
    filename: str
    media_type: Literal["image", "audio", "video"]
    role: Literal["Evidence", "Reference", "Control"]
    size_bytes: int
    sha256: str
    hash_source: Literal["client_declared"] = "client_declared"
    registered_at: datetime
    registered_by: str
    registered_by_verified: Literal[False] = False
    preserved: Literal[False] = False
    preserved_evidence_id: None = None
    duplicate_hash_of: list[str] = Field(default_factory=list)


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    total: int
