import hashlib
import io
from pathlib import Path
from functools import lru_cache
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile, status

from fastapi.responses import FileResponse
from PIL import Image
from provenance_store import ProvenanceStore
from provenance import MAX_BYTES, validate_preview_image, oriented_preview, jpeg_preview_response

from .models import (
    CaseDetailResponse,
    CaseEventListResponse,
    CaseListResponse,
    CaseResponse,
    CreateFindingNoteRequest,
    CreateCaseRequest,
    EvidenceListResponse,
    EvidenceResponse,
    EvidenceReceipt,
    FindingNoteListResponse,
    FindingNoteResponse,
    FindingListResponse,
    FindingResponse,
    RegisterFindingRequest,
    RegisterEvidenceRequest,
)
from .repository import (
    CaseNotFoundError,
    CaseRepository,
    DuplicateEvidenceError,
    FindingConflictError,
    FindingNotFoundError,
)


@lru_cache(maxsize=1)
def get_case_repository() -> CaseRepository:
    return CaseRepository()


def _analyst_name(value: str | None) -> str:
    if not value or not value.strip():
        return "Demo analyst"
    value = value.strip()
    if len(value) > 200 or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid X-Analyst-Name header")
    return value


def create_cases_router(repository: CaseRepository | None = None) -> APIRouter:
    cases_router = APIRouter(tags=["cases"])

    def store() -> CaseRepository:
        return repository or get_case_repository()

    @cases_router.post("/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
    def create_case(
        payload: CreateCaseRequest,
        x_analyst_name: str | None = Header(default=None, alias="X-Analyst-Name"),
    ):
        return store().create_case(payload.title, payload.description, _analyst_name(x_analyst_name))

    @cases_router.get("/cases", response_model=CaseListResponse)
    def list_cases(
        q: str | None = Query(default=None, max_length=200),
        case_status: str | None = Query(default=None, alias="status", max_length=100),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        sort_by: Literal["last_activity_at", "created_at", "title"] = "last_activity_at",
        order: Literal["asc", "desc"] = "desc",
    ):
        items, total = store().list_cases(q, case_status, limit, offset, sort_by, order)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @cases_router.get("/cases/{case_id}/events", response_model=CaseEventListResponse)
    def list_case_events(
        case_id: str,
        event_type: list[str] | None = Query(default=None, alias="type"),
        evidence_id: str | None = Query(default=None, max_length=100),
        run_id: str | None = Query(default=None, max_length=100),
        actor: str | None = Query(default=None, max_length=200),
        from_at: datetime | None = Query(default=None, alias="from"),
        to_at: datetime | None = Query(default=None, alias="to"),
        limit: int = Query(default=25, ge=1, le=100),
        cursor: str | None = Query(default=None),
    ):
        types = [item for value in event_type or [] for item in value.split(",") if item]
        try:
            items, next_cursor = store().query_events(
                case_id, types, evidence_id, run_id, actor,
                from_at.isoformat().replace("+00:00", "Z") if from_at else None,
                to_at.isoformat().replace("+00:00", "Z") if to_at else None,
                limit, cursor,
            )
        except CaseNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case '{case_id}' was not found")
        except ValueError as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))
        return {"items": items, "next_cursor": next_cursor}

    @cases_router.get("/cases/{case_id}", response_model=CaseDetailResponse)
    def get_case(case_id: str):
        record = store().get_case(case_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case '{case_id}' was not found")
        return record

    @cases_router.post(
        "/cases/{case_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED
    )
    def register_evidence(
        case_id: str,
        payload: RegisterEvidenceRequest,
        x_analyst_name: str | None = Header(default=None, alias="X-Analyst-Name"),
    ):
        try:
            return store().register_evidence(case_id, payload.model_dump(), _analyst_name(x_analyst_name))
        except CaseNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case '{case_id}' was not found")
        except DuplicateEvidenceError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Evidence ID '{error.args[0]}' already exists in case '{case_id}'",
            )

    @cases_router.post("/cases/{case_id}/originals", response_model=EvidenceResponse, status_code=201)
    def preserve_case_original(
        case_id: str, file: UploadFile = File(...),
        supplied_by: str = Form("", max_length=200),
        collection_reference: str = Form("", max_length=200),
        receipt_note: str = Form("", max_length=1000),
        x_analyst_name: str | None = Header(default=None, alias="X-Analyst-Name"),
    ):
        actor = _analyst_name(x_analyst_name)
        try:
            if store().get_case(case_id) is None:
                raise HTTPException(404, "Case not found")
            name = (file.filename or "").replace(chr(92), "/").rsplit("/", 1)[-1]
            extension = Path(name).suffix.lower()
            raw = file.file.read(MAX_BYTES + 1)
            if not raw or len(raw) > MAX_BYTES:
                raise HTTPException(413, "Choose a nonempty file up to 15 MiB.")
            media_type = "image"
            if extension == ".mp4":
                if raw[4:8] != b"ftyp":
                    raise ValueError("MP4 header is missing.")
                media_type = "video"
            elif extension in (".wav", ".mp3"):
                from provenance_tools import inspect_audio
                inspect_audio(raw, name, "intake")
                media_type = "audio"
            elif extension in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"):
                with Image.open(io.BytesIO(raw)) as image:
                    validate_preview_image(image)
                    image.verify()
            else:
                raise ValueError("Choose JPEG, PNG, WebP, HEIC, WAV, MP3 or MP4.")
            payload = RegisterEvidenceRequest(filename=name, media_type=media_type, role="Evidence",
                                              size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            receipt = EvidenceReceipt(supplied_by=supplied_by, collection_reference=collection_reference,
                                      note=receipt_note).model_dump()
            digest = ProvenanceStore().preserve(raw)
            return store().register_evidence(case_id, payload.model_dump(), actor, preserved_hash=digest,
                                             receipt=receipt if any(receipt.values()) else None)
        except CaseNotFoundError as error:
            raise HTTPException(404, "Case not found") from error
        except (ValueError, OSError, Image.DecompressionBombError) as error:
            raise HTTPException(400, str(error)) from error
        finally:
            file.file.close()

    @cases_router.get("/cases/{case_id}/originals/{evidence_id}")
    def case_original(case_id: str, evidence_id: str, preview: bool = False):
        try:
            record = next((item for item in store().list_evidence(case_id)
                           if item["evidence_id"] == evidence_id and item["preserved"]), None)
        except CaseNotFoundError as error:
            raise HTTPException(404, "Case not found") from error
        if not record:
            raise HTTPException(404, "Preserved case original not found")
        path = ProvenanceStore().blob_path(record["sha256"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise HTTPException(409, "Preserved case original failed SHA-256 verification")
        if preview and record["media_type"] == "image":
            with Image.open(path) as image:
                return jpeg_preview_response(oriented_preview(image))
        from mimetypes import guess_type
        return FileResponse(path, media_type=guess_type(record["filename"])[0] or "application/octet-stream",
                            headers={"Cache-Control": "no-store"})

    @cases_router.get("/cases/{case_id}/evidence", response_model=EvidenceListResponse)
    def list_evidence(
        case_id: str,
        role: Literal["Evidence", "Reference", "Control"] | None = None,
        media_type: Literal["image", "audio", "video"] | None = None,
    ):
        try:
            items = store().list_evidence(case_id, role, media_type)
        except CaseNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case '{case_id}' was not found")
        return {"items": items, "total": len(items)}

    @cases_router.post("/findings", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
    def register_finding(payload: RegisterFindingRequest):
        try:
            return store().register_finding(payload.finding, payload.case_id)
        except CaseNotFoundError:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "The case/evidence relationship for this finding was not found",
            )
        except FindingConflictError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Finding '{error.args[0]}' is already registered with different content",
            )
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))

    @cases_router.get("/findings", response_model=FindingListResponse)
    def list_findings(
        case_id: str | None = Query(default=None, max_length=100),
        evidence_id: str | None = Query(default=None, max_length=100),
    ):
        try:
            items = store().list_findings(case_id, evidence_id)
        except CaseNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case '{case_id}' was not found")
        return {"items": items, "total": len(items)}

    @cases_router.post(
        "/findings/{finding_id}/notes",
        response_model=FindingNoteResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def add_finding_note(
        finding_id: str,
        payload: CreateFindingNoteRequest,
        x_analyst_name: str | None = Header(default=None, alias="X-Analyst-Name"),
    ):
        try:
            return store().add_finding_note(
                finding_id, payload.status, payload.text, _analyst_name(x_analyst_name)
            )
        except FindingNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Finding '{finding_id}' was not found")

    @cases_router.get("/findings/{finding_id}/notes", response_model=FindingNoteListResponse)
    def list_finding_notes(finding_id: str):
        try:
            items = store().list_finding_notes(finding_id)
        except FindingNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Finding '{finding_id}' was not found")
        return {"items": items, "total": len(items)}

    return cases_router


router = create_cases_router()
