from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, status

from .models import (
    CaseDetailResponse,
    CaseListResponse,
    CaseResponse,
    CreateCaseRequest,
    EvidenceListResponse,
    EvidenceResponse,
    RegisterEvidenceRequest,
)
from .repository import CaseNotFoundError, CaseRepository, DuplicateEvidenceError


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
    ):
        items, total = store().list_cases(q, case_status, limit, offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

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

    return cases_router


router = create_cases_router()
