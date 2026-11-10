"""D1 Day 2-3 candidate analysis API. Uploaded originals are not retained."""
import hashlib
import io
import json
import math
import time
import uuid
import warnings
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from threading import BoundedSemaphore

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from detector import ImageDetector, LIMITATIONS, MODEL_ID, REVISION, model_files_present


ROOT = Path(__file__).parent
MAX_BYTES = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
SLOTS = BoundedSemaphore(1)
detector = ImageDetector()
app = FastAPI(title="Pratyaksh D1", version="0.3.0")


@app.get("/")
def home():
    return {"service": "Pratyaksh D1", "documentation": "/docs"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "pratyaksh-d1",
        "stage": "day23-image-candidate",
        "contract_version": "1.0",
        "detector_ready": detector.backbone is not None,
        "model_files_present": model_files_present(),
    }


@app.get("/api/capabilities")
def capabilities():
    return {
        "contract_version": "1.0",
        "image": {
            "implemented": True,
            "loaded": detector.backbone is not None,
            "model_files_present": model_files_present(),
            "evaluated": False,
            "selection_state": "day23_candidate_unevaluated",
            "candidate": MODEL_ID,
            "formats": ["JPEG", "PNG", "WEBP"],
            "max_bytes": MAX_BYTES,
        },
        "video": {"ready": False, "selection_state": "planned"},
        "audio": {"ready": False, "selection_state": "candidate_probe_pending"},
    }


@app.post("/api/d1/analyze-image")
def analyze_image(file: UploadFile = File(...)):
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, "An image is already being processed; try again shortly.")
    started = time.perf_counter()
    try:
        raw = file.file.read(MAX_BYTES + 1)
        if not raw:
            raise HTTPException(400, "Empty file")
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 15 MiB")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as source:
                    if source.format not in {"JPEG", "PNG", "WEBP"}:
                        raise HTTPException(415, "Only JPEG, PNG and WEBP are supported")
                    if getattr(source, "n_frames", 1) != 1:
                        raise HTTPException(415, "Animated images are unsupported")
                    source.load()
                    image = ImageOps.exif_transpose(source).convert("RGB")
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            raise HTTPException(422, "Image cannot be safely decoded or exceeds the pixel limit")
        if min(image.size) < 32:
            raise HTTPException(422, "Image must be at least 32 pixels in each dimension")
        try:
            prediction = detector.predict(image)
        except (ImportError, FileNotFoundError, OSError, ValueError, KeyError):
            raise HTTPException(
                503,
                "Detector unavailable. Install requirements and run python setup_day23_models.py.",
            )
        except Exception:
            raise HTTPException(500, "Inference failed. No classification was produced.")
        score = float(prediction["deepfake_score"])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise HTTPException(500, "Detector returned an invalid score; no result saved")

        run_id = "RUN-" + uuid.uuid4().hex
        finding = {
            "schema_version": "1.0",
            "finding_id": "F-" + uuid.uuid4().hex,
            "run_id": run_id,
            "evidence_id": "LOCAL-" + uuid.uuid4().hex,
            "category": "synthetic_media",
            "execution_status": "completed",
            "result": "inconclusive",
            "observation": "Day 2-3 candidate image model ran; project validation is required.",
            "method": MODEL_ID,
            "method_version": REVISION,
            "scope": "Whole decoded image; no region localization",
            "score": {
                "value": score,
                "range": [0, 1],
                "positive_class": "Deepfake",
                "interpretation": "Sigmoid classifier output, not probability that evidence is fake",
                "calibration_status": "Not calibrated on project data",
            },
            "location": None,
            "support_refs": [],
            "limitations": LIMITATIONS,
            "review_status": "unreviewed",
            "fixture": False,
        }
        response = {
            "finding": finding,
            "input": {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "width": image.width,
                "height": image.height,
                "original_retained": False,
                "evidence_id_is_session_local": True,
            },
            "model": prediction,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "runtime_ms": round((time.perf_counter() - started) * 1000),
            "environment": {
                package: version(package) for package in ("torch", "torchvision", "Pillow")
            },
            "threshold": None,
            "preprocessing_version": "ufd-center-crop-224-clip-normalize-v1",
        }
        destination = ROOT / "data" / "runs"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"{run_id}.json").write_text(
            json.dumps(response, indent=2), encoding="utf-8"
        )
        return response
    finally:
        file.file.close()
        SLOTS.release()
