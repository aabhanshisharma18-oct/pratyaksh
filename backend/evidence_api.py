"""Local evidence intake and integrity verification for the PRATYAKSH prototype."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

app = FastAPI(title="PRATYAKSH Evidence Intake")
STORE = Path(os.environ.get("PRATYAKSH_EVIDENCE_DIR", Path(__file__).parent / "data" / "evidence"))
MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 20_000_000
FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
CHUNK_SIZE = 256 * 1024


def read_record(folder: Path) -> dict:
    return json.loads((folder / "record.json").read_text(encoding="utf-8"))


def find_record(evidence_id: str) -> tuple[Path, dict]:
    folder = STORE / evidence_id
    if not re.fullmatch(r"EVID-[a-f0-9]{32}", evidence_id) or not (folder / "record.json").is_file():
        raise HTTPException(404, "Evidence record not found.")
    return folder, read_record(folder)


@app.post("/api/evidence", status_code=201)
def intake(
    file: Annotated[UploadFile, File()],
    case_id: Annotated[str, Form(pattern=r"^CASE-[0-9]{4}-[0-9]{3,12}$")],
    receipt_context: Annotated[str, Form(max_length=1000)] = "",
):
    STORE.mkdir(parents=True, exist_ok=True)
    evidence_id = "EVID-" + uuid.uuid4().hex
    staging = Path(tempfile.mkdtemp(prefix=".intake-", dir=STORE))
    try:
        original = staging / "original"
        digest = hashlib.sha256()
        size = 0
        with original.open("xb") as target:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "Image exceeds the 15 MiB intake limit.")
                target.write(chunk)
                digest.update(chunk)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(original) as image:
                    if (image.format not in FORMATS or image.width * image.height > MAX_PIXELS
                            or getattr(image, "is_animated", False)):
                        raise HTTPException(415, "Use a static JPEG, PNG or WebP up to 20 megapixels.")
                    media_type = FORMATS[image.format]
                    width, height = image.size
                    image.load()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as error:
            raise HTTPException(415, "Unable to decode a supported static image.") from error

        record = {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "filename": (file.filename or "image").replace("\\", "/").rsplit("/", 1)[-1][:255],
            "sha256": digest.hexdigest(),
            "received_at": datetime.now(timezone.utc).isoformat(),
            "receipt_context": receipt_context,
            "size_bytes": size,
            "media_type": media_type,
            "width": width,
            "height": height,
        }
        (staging / "record.json").write_text(json.dumps(record), encoding="utf-8")
        original.chmod(0o400)
        staging.rename(STORE / evidence_id)
        return record
    finally:
        if staging.exists():
            shutil.rmtree(staging)


@app.get("/api/evidence")
def list_evidence(case_id: str):
    records = [read_record(path.parent) for path in STORE.glob("EVID-*/record.json")]
    return sorted(
        (record for record in records if record["case_id"] == case_id),
        key=lambda record: record["received_at"],
    )


@app.get("/api/evidence/{evidence_id}/media")
def read_media(evidence_id: str):
    folder, record = find_record(evidence_id)
    if not (folder / "original").is_file():
        raise HTTPException(404, "Stored file is missing.")
    return FileResponse(folder / "original", media_type=record["media_type"], headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@app.post("/api/evidence/{evidence_id}/verify")
def verify(evidence_id: str):
    folder, record = find_record(evidence_id)
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        with (folder / "original").open("rb") as original:
            digest = hashlib.file_digest(original, "sha256").hexdigest()
    except OSError:
        digest = None
    status = "unavailable" if digest is None else "match" if digest == record["sha256"] else "mismatch"
    return {
        "evidence_id": evidence_id,
        "expected_sha256": record["sha256"],
        "actual_sha256": digest,
        "checked_at": checked_at,
        "status": status,
    }
