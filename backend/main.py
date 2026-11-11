"""D1 Day 2-3 candidate analysis API. Uploaded originals are not retained."""
import hashlib
import io
import json
import math
import os
import time
import uuid
import warnings
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from threading import BoundedSemaphore

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError

from cases import get_case_repository
from cases import router as cases_router
from detector import ImageDetector, LIMITATIONS, MODEL_ID, REVISION, model_files_present
from face_forgery_detector import (
    FaceForgeryDetector,
    LIMITATIONS as FACE_LIMITATIONS,
    MODEL_ID as FACE_MODEL_ID,
    MODEL_VERSION as FACE_MODEL_VERSION,
    face_model_files_present,
)
from audio_probe import (
    AASISTProbe,
    AudioProbeError,
    REVISION as AUDIO_REVISION,
    audio_probe_files_present,
)


ROOT = Path(__file__).parent
MAX_BYTES = 15 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
SLOTS = BoundedSemaphore(1)
detector = ImageDetector()
face_forgery_detector = FaceForgeryDetector()
audio_probe = AASISTProbe()
app = FastAPI(title="Pratyaksh D1", version="0.4.0")
case_repository = get_case_repository()
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "PRATYAKSH_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(cases_router, prefix="/api")


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
        "face_forgery_ready": face_forgery_detector.classifier is not None,
        "face_model_files_present": face_model_files_present(),
        "audio_probe_ready": audio_probe.model is not None,
        "audio_probe_files_present": audio_probe_files_present(),
        "case_store_ready": case_repository.ready(),
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
            "face_forgery": {
                "implemented": True,
                "loaded": face_forgery_detector.classifier is not None,
                "model_files_present": face_model_files_present(),
                "evaluated": False,
                "selection_state": "research_candidate_unevaluated",
                "candidate": FACE_MODEL_ID,
                "license": "Noncommercial research use only",
            },
        },
        "video": {"ready": False, "selection_state": "planned"},
        "audio": {
            "ready": audio_probe_files_present(),
            "implemented": True,
            "loaded": audio_probe.model is not None,
            "evaluated": False,
            "selection_state": "execution_probe_only",
            "candidate": "clovaai/AASIST",
            "formats": ["Any FFmpeg-decodable audio"],
            "max_bytes": MAX_AUDIO_BYTES,
            "reason": "Probe only; no calibrated voice-clone verdict",
        },
    }


def _decode_image_upload(file: UploadFile):
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
    return raw, image


@app.post("/api/d1/analyze-image")
def analyze_image(file: UploadFile = File(...)):
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, "An image is already being processed; try again shortly.")
    started = time.perf_counter()
    try:
        raw, image = _decode_image_upload(file)
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


@app.post("/api/d1/analyze-face-forgery")
def analyze_face_forgery(file: UploadFile = File(...)):
    """Run the optional face-specific research candidate without a final verdict."""
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, "A model is already being processed; try again shortly.")
    started = time.perf_counter()
    try:
        raw, image = _decode_image_upload(file)
        try:
            prediction = face_forgery_detector.predict(image)
        except (ImportError, FileNotFoundError, OSError, ValueError, KeyError):
            raise HTTPException(
                503,
                "Face-forgery candidate unavailable. Install requirements-face-research.txt "
                "and run setup_face_research_models.py with the licence acceptance flag.",
            )
        except Exception:
            raise HTTPException(500, "Face-forgery inference failed; no score was produced.")

        run_id = "RUN-" + uuid.uuid4().hex
        score = prediction.get("face_forgery_score")
        if prediction["execution_status"] == "completed":
            if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise HTTPException(500, "Face-forgery candidate returned an invalid score")
            observation = (
                f"Face-specific research candidate scored {prediction['face_count']} "
                "detected face(s); project validation is required."
            )
        else:
            score = None
            observation = "No face was detected; no face-forgery score was produced."

        response = {
            "finding": {
                "schema_version": "1.0",
                "finding_id": "F-" + uuid.uuid4().hex,
                "run_id": run_id,
                "evidence_id": "LOCAL-" + uuid.uuid4().hex,
                "category": "synthetic_media",
                "execution_status": prediction["execution_status"],
                "result": "inconclusive",
                "observation": observation,
                "method": FACE_MODEL_ID,
                "method_version": FACE_MODEL_VERSION,
                "scope": "YuNet-detected face crops; maximum face signal reported",
                "score": (
                    {
                        "value": float(score),
                        "range": [0, 1],
                        "positive_class": "Face forgery",
                        "interpretation": "Raw SBI softmax signal, not a probability of manipulation",
                        "calibration_status": "Not calibrated on project data",
                    }
                    if score is not None
                    else None
                ),
                "location": None,
                "support_refs": [],
                "limitations": FACE_LIMITATIONS,
                "review_status": "unreviewed",
                "fixture": False,
            },
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
            "threshold": None,
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


@app.post("/api/d1/probe-audio")
def probe_audio(file: UploadFile = File(...)):
    """Run the audio execution probe without producing a forensic finding."""
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, "A model is already being processed; try again shortly.")
    started = time.perf_counter()
    try:
        raw = file.file.read(MAX_AUDIO_BYTES + 1)
        if not raw:
            raise HTTPException(400, "Empty audio file")
        if len(raw) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Audio exceeds 25 MiB")
        try:
            output = audio_probe.probe(raw)
        except AudioProbeError as exc:
            raise HTTPException(422, str(exc))
        except (ImportError, FileNotFoundError, OSError, ValueError, KeyError):
            raise HTTPException(
                503,
                "Audio probe unavailable. Run python setup_day23_models.py and check FFmpeg.",
            )
        score = output["model"]["spoof_score"]
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise HTTPException(500, "Audio probe returned an invalid score")
        return {
            "schema_version": "1.0",
            "probe_status": "completed",
            "selection_state": "execution_probe_only",
            "result": "inconclusive",
            "observation": "AASIST executed successfully; this is not a voice-clone verdict.",
            "input": {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "original_retained": False,
            },
            "method": "clovaai/AASIST",
            "method_version": AUDIO_REVISION,
            "output": output,
            "runtime_ms": round((time.perf_counter() - started) * 1000),
            "threshold": None,
            "limitations": [
                "Execution probe only; not evaluated on the Pratyaksh held-out dataset.",
                "AASIST was trained for ASVspoof logical-access anti-spoofing and is not a universal voice-clone detector.",
                "Only the first 64,600 decoded samples (about 4.04 seconds) are scored.",
                "The raw spoof score is not a calibrated probability and must not be used as an authenticity verdict.",
            ],
        }
    finally:
        file.file.close()
        SLOTS.release()
