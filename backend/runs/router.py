from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from provenance_store import ProvenanceStore

from .repository import (
    AmbiguousEvidenceError,
    EvidenceNotFoundError,
    InvalidRetryError,
    RunNotFoundError,
    RunRepository,
)


RunWorker = Callable[[str], None]


class RunScheduler:
    def __init__(self, worker: RunWorker, max_workers: int = 2):
        self.worker = worker
        self.pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pratyaksh-run")

    def enqueue(self, run_id: str) -> None:
        self.pool.submit(self.worker, run_id)


def create_runs_router(repository: RunRepository, scheduler: RunScheduler, storage_root: Path) -> APIRouter:
    router = APIRouter(tags=["runs"])

    def translate(error: Exception):
        if isinstance(error, EvidenceNotFoundError):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence was not found")
        if isinstance(error, RunNotFoundError):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Run was not found")
        if isinstance(error, AmbiguousEvidenceError):
            raise HTTPException(status.HTTP_409_CONFLICT, "Evidence ID exists in more than one case; provide case_id")
        if isinstance(error, InvalidRetryError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))
        raise error

    @router.post("/evidence/{evidence_id}/runs", status_code=status.HTTP_202_ACCEPTED)
    def create_run(
        evidence_id: str,
        case_id: str | None = Form(default=None),
        retry_of_run_id: str | None = Form(default=None),
        retry_checks: str | None = Form(default=None),
        file: UploadFile | None = File(default=None),
    ):
        try:
            evidence = repository.resolve_evidence(evidence_id, case_id)
            checks = None
            if retry_checks:
                decoded = json.loads(retry_checks)
                if not isinstance(decoded, list) or not all(isinstance(item, str) and item for item in decoded):
                    raise InvalidRetryError("retry_checks must be a JSON array of check names")
                checks = decoded
            input_path = None
            if file is not None:
                raw = file.file.read(50 * 1024 * 1024 + 1)
                file.file.close()
                if not raw:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty evidence file")
                if len(raw) > 50 * 1024 * 1024:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Evidence exceeds 50 MiB")
                if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
                    raise HTTPException(status.HTTP_409_CONFLICT, "Uploaded analysis copy does not match the registered SHA-256")
                folder = storage_root / evidence["case_id"] / evidence_id
                folder.mkdir(parents=True, exist_ok=True)
                suffix = Path(evidence["filename"]).suffix.lower()
                suffix = suffix if suffix and len(suffix) <= 10 else ".media"
                destination = folder / ("analysis-copy" + suffix)
                destination.write_bytes(raw)
                input_path = str(destination)
            elif evidence.get("preserved_evidence_id"):
                original = ProvenanceStore().blob_path(evidence["sha256"])
                if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != evidence["sha256"]:
                    raise HTTPException(409, "Preserved case original failed SHA-256 verification")
                input_path = str(original)
            run = repository.create_run(evidence_id, evidence["case_id"], retry_of_run_id, checks, input_path)
            if not repository.input_path(run["run_id"]):
                for check in run["requested_checks"]:
                    repository.append_event(run["run_id"], check, "check.failed", "failed", {
                        "error": {"code": "INPUT_NOT_AVAILABLE", "message": "No persisted analysis copy is available for this run.", "retryable": True}
                    })
            else:
                scheduler.enqueue(run["run_id"])
            return repository.get_run(run["run_id"])
        except json.JSONDecodeError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "retry_checks must be valid JSON")
        except (EvidenceNotFoundError, RunNotFoundError, AmbiguousEvidenceError, InvalidRetryError) as error:
            translate(error)

    @router.get("/runs/{run_id}")
    def get_run(run_id: str):
        try:
            return repository.get_run(run_id)
        except RunNotFoundError as error:
            translate(error)

    @router.get("/evidence/{evidence_id}/runs")
    def list_runs(evidence_id: str, case_id: str | None = Query(default=None)):
        try:
            items = repository.list_runs(evidence_id, case_id)
            return {"items": items, "total": len(items)}
        except (EvidenceNotFoundError, AmbiguousEvidenceError) as error:
            translate(error)

    return router
