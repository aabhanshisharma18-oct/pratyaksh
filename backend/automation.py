"""Persistent ZIP intake and sequential case analysis using existing services."""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import stat
import subprocess
import tempfile
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from threading import Lock

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from PIL import Image
from cases.models import CreateCaseRequest
from cases.repository import utc_now
from provenance_store import ProvenanceStore

MAX_ZIP_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 60 * 1024 * 1024
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_MEDIA_FILES = 12


def archive_members(raw):
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
        entries = [item for item in archive.infolist() if not item.is_dir()]
        if not entries or len(entries) > 64:
            raise ValueError("Use a ZIP containing 1–64 entries, including up to 12 media files.")
        if sum(item.file_size for item in entries) > MAX_TOTAL_BYTES:
            raise ValueError("Uncompressed ZIP contents exceed 60 MiB.")
        names = set()
        for item in entries:
            name = item.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or ":" in name or name in names:
                raise ValueError("ZIP contains an unsafe or duplicate path.")
            names.add(name)
            if stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                raise ValueError("Use ordinary, unencrypted files in the ZIP.")
            if item.file_size > MAX_FILE_BYTES:
                raise ValueError("Each ZIP entry must be at most 15 MiB.")
        return archive, entries
    except zipfile.BadZipFile as error:
        raise ValueError("The uploaded file is not a readable ZIP.") from error


def classify(raw):
    """Inspect decoded content, independent of the submitted extension."""
    from provenance import validate_preview_image
    try:
        with Image.open(io.BytesIO(raw)) as image:
            validate_preview_image(image)
            image.verify()
            return "image"
    except (OSError, ValueError, SyntaxError):
        pass
    with tempfile.NamedTemporaryFile(suffix=".media") as stream:
        stream.write(raw)
        stream.flush()
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                 "-of", "json", stream.name], capture_output=True, timeout=20, check=False,
            )
            if result.returncode:
                return None
            kinds = {item.get("codec_type") for item in json.loads(result.stdout).get("streams", [])}
            if "video" in kinds:
                return "video"
            if "audio" in kinds:
                return "audio"
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return None
    return None


class CaseAutomation:
    def __init__(self, cases, runs, worker, authenticate, relate):
        self.cases, self.runs = cases, runs
        self.worker, self.authenticate, self.relate = worker, authenticate, relate
        self.database = cases.database_path
        self.root = Path(self.database).parent / "automation"
        self.root.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="case-automation")
        self.lock = Lock()
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS case_automation (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, request_key TEXT UNIQUE, document TEXT NOT NULL)")
            for job_id, document in db.execute("SELECT id,document FROM case_automation").fetchall():
                job = json.loads(document)
                if job["status"] in {"queued", "running"}:
                    job["status"] = "interrupted"
                    job["message"] = "The service restarted. Resume the saved analysis."
                    db.execute("UPDATE case_automation SET document=? WHERE id=?", (json.dumps(job), job_id))

    def save(self, job):
        job["updated_at"] = utc_now()
        with sqlite3.connect(self.database, timeout=30) as db:
            db.execute("UPDATE case_automation SET document=? WHERE id=?", (json.dumps(job), job["id"]))

    def get(self, job_id):
        with sqlite3.connect(self.database) as db:
            row = db.execute("SELECT document FROM case_automation WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Automation job not found")
        return json.loads(row[0])

    def latest(self, case_id):
        with sqlite3.connect(self.database) as db:
            row = db.execute("SELECT document FROM case_automation WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def submit(self, raw, title, description, actor, request_key):
        digest = hashlib.sha256(raw).hexdigest()
        with self.lock:
            with sqlite3.connect(self.database) as db:
                row = db.execute("SELECT document FROM case_automation WHERE request_key=?", (request_key,)).fetchone()
            if row:
                previous = json.loads(row[0])
                if previous["archive_sha256"] != digest or previous["title"] != title:
                    raise HTTPException(409, "This upload request ID belongs to a different archive or title.")
                return previous
            archive, entries = archive_members(raw)
            archive.close()
            job_id = "AUTO-" + uuid.uuid4().hex
            destination = self.root / (job_id + ".zip")
            destination.write_bytes(raw)
            destination.chmod(0o444)
            case = self.cases.create_case(title, description, actor)
            job = {"id": job_id, "case_id": case["id"], "title": title, "actor": actor,
                   "status": "queued", "message": "Waiting to inspect archive contents",
                   "archive_sha256": digest, "created_at": utc_now(), "files": [],
                   "entry_count": len(entries), "provenance": {"status": "pending"},
                   "report": {"status": "pending"}}
            with sqlite3.connect(self.database) as db:
                db.execute("INSERT INTO case_automation VALUES (?,?,?,?)",
                           (job_id, case["id"], request_key, json.dumps(job)))
            self.pool.submit(self.run, job_id)
            return job

    def retry(self, job_id):
        with self.lock:
            job = self.get(job_id)
            if job["status"] in {"queued", "running"}:
                raise HTTPException(409, "This job is already processing.")
            job["status"] = "queued"
            self.save(job)
            self.pool.submit(self.run, job_id)
            return job

    def step(self, job, item, key, action):
        if item.get(key, {}).get("status") == "completed":
            return
        item[key] = {"status": "running"}
        job["message"] = key.replace("_", " ").title() + " · " + item.get("name", "case")
        self.save(job)
        try:
            value = action()
            item[key] = {"status": "completed", "result": value}
        except Exception as error:
            message = str(getattr(error, "detail", error))[:600]
            item[key] = {"status": "failed", "error": message}
        self.save(job)

    def run(self, job_id):
        job = self.get(job_id)
        job["status"] = "running"
        self.save(job)
        try:
            raw = (self.root / (job_id + ".zip")).read_bytes()
            if hashlib.sha256(raw).hexdigest() != job["archive_sha256"]:
                raise ValueError("Stored ZIP fingerprint verification failed.")
            archive, entries = archive_members(raw)
            with archive:
                if not job["files"]:
                    for entry in entries:
                        if entry.filename.startswith("__MACOSX/") or PurePosixPath(entry.filename).name.startswith("."):
                            continue
                        content = archive.read(entry)
                        kind = classify(content) if content else None
                        job["files"].append({"name": entry.filename, "media_type": kind,
                            "status": "pending" if kind else "skipped",
                            "reason": None if kind else "Unsupported or unreadable media; retained in submitted ZIP."})
                    if sum(bool(item["media_type"]) for item in job["files"]) > MAX_MEDIA_FILES:
                        raise ValueError("This workflow supports up to 12 media files per archive.")
                    self.save(job)
                for index, item in enumerate(job["files"]):
                    if not item["media_type"]:
                        continue
                    content = archive.read(item["name"])
                    digest = ProvenanceStore().preserve(content)
                    evidence_id = job["id"] + "-" + str(index)
                    existing = next((e for e in self.cases.list_evidence(job["case_id"]) if e["evidence_id"] == evidence_id), None)
                    evidence = existing or self.cases.register_evidence(job["case_id"], {
                        "evidence_id": evidence_id, "filename": PurePosixPath(item["name"]).name,
                        "media_type": item["media_type"], "role": "Evidence",
                        "size_bytes": len(content), "sha256": digest,
                    }, job["actor"], preserved_hash=digest, receipt={
                        "supplied_by": job["actor"], "collection_reference": job["id"],
                        "note": "ZIP member: " + item["name"],
                    })
                    item["evidence_id"] = evidence_id
                    self.save(job)

                    def detect():
                        previous = item.get("run_id")
                        if previous and self.runs.get_run(previous)["execution_status"] == "completed":
                            return {"run_id": previous}
                        run = self.runs.create_run(evidence_id, job["case_id"],
                            retry_of_run_id=previous, input_path=str(ProvenanceStore().blob_path(digest)))
                        item["run_id"] = run["run_id"]
                        self.save(job)
                        self.worker(run["run_id"])
                        result = self.runs.get_run(run["run_id"])
                        if result["execution_status"] != "completed":
                            raise ValueError("Detection run " + result["execution_status"] + "; see saved findings and run errors.")
                        return {"run_id": run["run_id"]}

                    self.step(job, item, "detection", detect)
                    self.step(job, item, "authentication",
                              lambda: self.authenticate(job, item, evidence, content))
                    item["status"] = "completed" if all(item[key]["status"] == "completed" for key in ("detection", "authentication")) else "partial"
                    self.save(job)
            selected = [item for item in job["files"] if item.get("evidence_id")]
            if len(selected) >= 2:
                self.step(job, job, "provenance", lambda: self.relate(job, selected))
            else:
                job["provenance"] = {"status": "skipped", "reason": "At least two supported files are required."}
            from reports.store import ReportStore
            self.step(job, job, "report", lambda: {
                "report_id": ReportStore(self.cases, run_reader=self.runs).create(
                    job["case_id"], job["actor"])["snapshot"]["report_id"]})
            failures = any(item.get("status") in {"failed", "partial", "skipped"} for item in job["files"])
            failures |= any(job[key]["status"] == "failed" for key in ("provenance", "report"))
            job["status"] = "partial" if failures else "completed"
            job["message"] = "Processing finished. Review the saved findings and limitations."
        except Exception as error:
            job["status"] = "failed"
            job["message"] = str(getattr(error, "detail", error))[:600]
        self.save(job)


def create_automation_router(service):
    router = APIRouter(tags=["automated case intake"])

    @router.post("/cases/from-zip", status_code=202)
    def upload_case_zip(file: UploadFile = File(...), title: str = Form(...),
                        description: str = Form(""), request_key: str = Form(..., min_length=1, max_length=100),
                        x_analyst_name: str = Header("Local analyst")):
        from cases.router import _analyst_name
        try:
            payload = CreateCaseRequest(title=title, description=description)
            raw = file.file.read(MAX_ZIP_BYTES + 1)
            if not raw or len(raw) > MAX_ZIP_BYTES:
                raise HTTPException(413, "Use a nonempty ZIP up to 64 MiB.")
            return service.submit(raw, payload.title, payload.description, _analyst_name(x_analyst_name), request_key)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            file.file.close()

    @router.get("/cases/{case_id}/automation")
    def get_case_automation(case_id: str):
        if not service.cases.get_case(case_id):
            raise HTTPException(404, "Case not found")
        return {"job": service.latest(case_id)}

    @router.post("/automation/{job_id}/resume", status_code=202)
    def resume_case_automation(job_id: str):
        return service.retry(job_id)

    return router
