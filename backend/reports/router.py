from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from cases.repository import CaseNotFoundError
from .store import ReportStore, canonical


class CreateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preparer: str = Field(min_length=1, max_length=200)
    sections: list[str] | None = Field(default=None, min_length=1, max_length=6)
    run_ids: list[str] | None = Field(default=None, min_length=1, max_length=1000)
    questions: str | None = Field(default=None, max_length=2000)
    next_steps: str | None = Field(default=None, max_length=2000)
    include_artifacts: bool = False


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer: str = Field(min_length=1, max_length=200)
    status: Literal["reviewed", "questioned"]
    note: str = Field(min_length=1, max_length=2000)


def create_reports_router(cases, run_reader=None, artifact_reader=None):
    router = APIRouter(prefix="/api", tags=["D5 reports"])

    def store():
        return ReportStore(cases, run_reader=run_reader, artifact_reader=artifact_reader)

    def saved(report_id):
        try:
            return store().get(report_id)
        except KeyError:
            raise HTTPException(404, "Report not found")
        except ValueError as error:
            raise HTTPException(409, str(error))

    @router.post("/cases/{case_id}/reports", status_code=201)
    def create(case_id: str, payload: CreateReport):
        try:
            return store().create(case_id, payload.preparer, payload.run_ids, payload.sections,
                                  payload.questions, payload.next_steps, payload.include_artifacts)
        except CaseNotFoundError:
            raise HTTPException(404, "Case not found")
        except ValueError as error:
            raise HTTPException(422, str(error))

    @router.get("/cases/{case_id}/reports/run-options")
    def run_options(case_id: str):
        try:
            return {"items": store().run_options(case_id)}
        except CaseNotFoundError:
            raise HTTPException(404, "Case not found")

    @router.get("/cases/{case_id}/reports")
    def revisions(case_id: str):
        try:
            return {"items": store().list(case_id)}
        except CaseNotFoundError:
            raise HTTPException(404, "Case not found")

    @router.get("/reports/{report_id}")
    def retrieve(report_id: str):
        return saved(report_id)

    @router.post("/reports/{report_id}/reviews", status_code=201)
    def review(report_id: str, payload: ReviewReport):
        saved(report_id)  # Missing/corrupt parent returns 404/409 before writing.
        try:
            return store().review(report_id, payload.reviewer, payload.status, payload.note)
        except ValueError as error:
            raise HTTPException(422, str(error))

    @router.get("/reports/{report_id}/export")
    def export(report_id: str, format: str = "json"):
        record = saved(report_id)
        if format not in ("json", "zip"):
            raise HTTPException(422, "Choose json or zip")
        try:
            raw = canonical(record["snapshot"]) if format == "json" else store().export(report_id)
        except ValueError as error:
            raise HTTPException(409, str(error))
        return Response(raw, media_type="application/json" if format == "json" else "application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{record["snapshot"]["report_id"]}.{format}"',
                                 "X-Report-SHA256": record["sha256"], "Cache-Control": "no-store"})

    return router
