from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _reject_control_characters(value: str, *, multiline: bool = False) -> str:
    allowed = {9, 10} if multiline else set()
    if any((ord(character) < 32 and ord(character) not in allowed) or ord(character) == 127 for character in value):
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
    last_activity_at: datetime
    evidence_count: int = 0
    created_by: str
    created_by_verified: Literal[False] = False


class EvidenceSummary(BaseModel):
    image: int = 0
    audio: int = 0
    video: int = 0


class CaseDetailResponse(CaseResponse):
    evidence_by_media_type: EvidenceSummary


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    limit: int
    offset: int


class CaseEventResponse(BaseModel):
    id: str
    type: Literal[
        "case.created", "evidence.registered", "run.started", "run.completed",
        "run.failed", "run.partial", "note.added", "finding.created",
    ]
    case_id: str
    evidence_id: str | None
    run_id: str | None
    actor: str
    created_at: datetime
    summary: str
    payload: dict[str, Any]


class CaseEventListResponse(BaseModel):
    items: list[CaseEventResponse]
    next_cursor: str | None


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


class EvidenceReceipt(BaseModel):
    supplied_by: str = Field(default="", max_length=200)
    collection_reference: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=1000)

    @field_validator("supplied_by", "collection_reference", "note")
    @classmethod
    def validate_receipt_text(cls, value: str) -> str:
        return _reject_control_characters(value.strip(), multiline=True)


class EvidenceResponse(BaseModel):
    case_id: str
    evidence_id: str
    filename: str
    media_type: Literal["image", "audio", "video"]
    role: Literal["Evidence", "Reference", "Control"]
    size_bytes: int
    sha256: str
    hash_source: Literal["client_declared", "server_computed"] = "client_declared"
    registered_at: datetime
    registered_by: str
    registered_by_verified: Literal[False] = False
    preserved: bool = False
    preserved_evidence_id: str | None = None
    duplicate_hash_of: list[str] = Field(default_factory=list)
    receipt: EvidenceReceipt | None = None


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    total: int


class RegisterFindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str | None = Field(default=None, min_length=1, max_length=100)
    finding: dict[str, Any]

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _reject_control_characters(value.strip())


class FindingResponse(BaseModel):
    finding_id: str
    evidence_id: str
    run_id: str
    case_id: str | None
    recorded_at: datetime
    finding_sha256: str
    finding: dict[str, Any]


class FindingListResponse(BaseModel):
    items: list[FindingResponse]
    total: int


class CreateFindingNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["reviewed", "questioned"]
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return _reject_control_characters(value, multiline=True)


class FindingNoteResponse(BaseModel):
    note_id: str
    finding_id: str
    finding_sha256: str
    status: Literal["reviewed", "questioned"]
    text: str
    author: str
    author_verified: Literal[False] = False
    created_at: datetime


class FindingNoteListResponse(BaseModel):
    items: list[FindingNoteResponse]
    total: int
