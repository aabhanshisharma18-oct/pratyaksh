"""D1 Day 2-3 candidate analysis API. Uploaded originals are not retained."""
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
from face_score_stability import compare_face_scores

from provenance import router as provenance_router, FORMATS as PROVENANCE_IMAGE_FORMATS, latest_case_analysis
from case_briefing import create_briefing_router
from automation import CaseAutomation, create_automation_router
from automation_checks import authenticate as authenticate_zip_item, relate as relate_zip_items
from cases import get_case_repository
from cases import router as cases_router
from reports.router import create_reports_router
from reports.artifacts import D2ReportArtifacts
from d2.api.router import services as d2_services
from runs.repository import RunRepository
from runs.router import RunScheduler, create_runs_router
from runs.video_mapper import map_video_response
from detector import ImageDetector, LIMITATIONS, MODEL_ID, REVISION, model_files_present
from face_forgery_detector import (
    FaceForgeryDetector,
    LIMITATIONS as FACE_LIMITATIONS,
)
from audio_probe import (
    AASISTProbe,
    AudioProbeError,
    REVISION as AUDIO_REVISION,
    audio_probe_files_present,
)
from video_probe import MAX_DURATION_SECONDS, VideoProbeError, VideoSampler
from d2 import router as d2_router


ROOT = Path(__file__).parent
MAX_BYTES = 15 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
SLOTS = BoundedSemaphore(1)
detector = ImageDetector()
face_forgery_detector = FaceForgeryDetector(
    use_pilot=os.getenv("PRATYAKSH_SBI_PILOT") == "1",
    use_still_images=os.getenv("PRATYAKSH_SBI_PILOT") == "still-images",
)
audio_probe = AASISTProbe()
video_sampler = VideoSampler()
E2E_STUB_ENABLED = os.getenv("PRATYAKSH_E2E_STUB") == "1"
if E2E_STUB_ENABLED and os.getenv("PRATYAKSH_ENV") != "test":
    raise RuntimeError("PRATYAKSH_E2E_STUB may only be enabled when PRATYAKSH_ENV=test")
app = FastAPI(title="Pratyaksh D1", version="0.5.0")
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
    expose_headers=["X-Manifest-SHA256", "X-Report-SHA256", "X-PDF-SHA256"],
)
app.include_router(cases_router, prefix="/api")
app.include_router(provenance_router)
app.include_router(d2_router)


@app.get("/")
def home():
    return {"service": "Pratyaksh D1", "documentation": "/docs"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "pratyaksh-d1",
        "stage": "day45-video-baseline",
        "contract_version": "1.0",
        "detector_ready": detector.backbone is not None,
        "model_files_present": model_files_present(),
        "face_forgery_ready": face_forgery_detector.classifier is not None,
        "face_model_files_present": face_forgery_detector.files_present(),
        "audio_probe_ready": audio_probe.model is not None,
        "audio_probe_files_present": audio_probe_files_present(),
        "video_tools_ready": video_sampler.available(),
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
                "model_files_present": face_forgery_detector.files_present(),
                "evaluated": False,
                "selection_state": "research_candidate_unevaluated",
                "candidate": face_forgery_detector.model_id,
                "license": "Noncommercial research use only",
            },
        },
        "video": {
            "ready": video_sampler.available() and model_files_present(),
            "implemented": True,
            "loaded": detector.backbone is not None,
            "evaluated": False,
            "selection_state": "day45_candidate_unevaluated",
            "candidate": f"Timestamp sampling + {MODEL_ID}",
            "formats": ["Any FFmpeg-decodable video"],
            "max_bytes": MAX_VIDEO_BYTES,
            "max_duration_seconds": MAX_DURATION_SECONDS,
            "max_sampled_frames": 12,
            "reason": "Frame-level candidate only; no validated video threshold or aggregation",
        },
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
                if source.format not in PROVENANCE_IMAGE_FORMATS:
                    raise HTTPException(415, "Use JPEG, PNG, WebP or an installed HEIC decoder")
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


@app.post("/api/d1/analyze-video")
def analyze_video(file: UploadFile = File(...)):
    """Sample timestamped frames and return an uncalibrated video-level signal."""
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, "Another detector request is being processed; try again shortly.")
    started = time.perf_counter()
    sampled = None
    try:
        raw = file.file.read(MAX_VIDEO_BYTES + 1)
        if not raw:
            raise HTTPException(400, "Empty file")
        if len(raw) > MAX_VIDEO_BYTES:
            raise HTTPException(413, "Video exceeds 50 MiB")
        try:
            sampled = video_sampler.sample(raw, file.filename)
        except VideoProbeError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc

        sample_results = []
        rejected = list(sampled["rejected"])
        for index, frame in enumerate(sampled["frames"], start=1):
            timestamp_ms = frame["timestamp_ms"]
            try:
                prediction = detector.predict(frame["image"])
            except (ImportError, FileNotFoundError, OSError, ValueError, KeyError) as exc:
                raise HTTPException(
                    503,
                    "Detector unavailable. Install requirements and run python setup_day23_models.py.",
                ) from exc
            except Exception:
                rejected.append({"timestamp_ms": timestamp_ms, "reason": "inference_failed"})
                continue
            try:
                score = float(prediction["deepfake_score"])
            except (KeyError, TypeError, ValueError):
                rejected.append({"timestamp_ms": timestamp_ms, "reason": "invalid_model_score"})
                continue
            if not math.isfinite(score) or not 0 <= score <= 1:
                rejected.append({"timestamp_ms": timestamp_ms, "reason": "invalid_model_score"})
                continue
            sample_results.append(
                {
                    "sample_id": f"FRAME-{index:03d}",
                    "timestamp_ms": timestamp_ms,
                    "deepfake_score": score,
                    "raw_logit": prediction.get("raw_logit"),
                }
            )

        if not sample_results:
            raise HTTPException(500, "No sampled frame produced a valid model output")

        scores = [sample["deepfake_score"] for sample in sample_results]
        mean_score = sum(scores) / len(scores)
        max_score = max(scores)
        run_id = "RUN-" + uuid.uuid4().hex
        evidence_id = "LOCAL-" + uuid.uuid4().hex
        finding = {
            "schema_version": "1.0",
            "finding_id": "F-" + uuid.uuid4().hex,
            "run_id": run_id,
            "evidence_id": evidence_id,
            "category": "synthetic_media",
            "execution_status": "completed",
            "result": "inconclusive",
            "observation": (
                f"Candidate image detector ran on {len(sample_results)} timestamped video frame(s); "
                "video-specific validation is required."
            ),
            "method": f"Timestamp sampling + {MODEL_ID}",
            "method_version": REVISION,
            "scope": "Bounded timestamp samples from the first video stream",
            "score": {
                "value": mean_score,
                "range": [0, 1],
                "positive_class": "Deepfake",
                "interpretation": (
                    "Unvalidated arithmetic mean of sampled-frame synthetic-image signals; "
                    "not a probability that the video is fake"
                ),
                "calibration_status": "No video threshold or aggregation calibrated",
            },
            "location": None,
            "support_refs": [sample["sample_id"] for sample in sample_results],
            "limitations": [
                "The underlying model is a whole-image AI-generation detector, not a video or temporal-consistency model.",
                "Only bounded timestamp samples are examined; manipulation between samples can be missed.",
                "The mean and maximum frame signals are unvalidated summaries and are not authenticity probabilities.",
                "Audio, lip synchronization, motion consistency and unsampled frames are not assessed.",
                "No video-specific held-out evaluation or decision threshold has been completed.",
            ],
            "review_status": "unreviewed",
            "fixture": False,
        }
        response = {
            "finding": finding,
            "input": {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "original_retained": False,
                "evidence_id_is_session_local": True,
            },
            "video": sampled["metadata"],
            "sampling": {
                "policy": "nearest presentation timestamp to the centre of each 2-second sampling bin",
                "maximum_samples": 12,
                "requested_samples": sampled["requested_count"],
                "examined_samples": len(sample_results),
                "rejected_samples": rejected,
                "coverage_fraction_of_requested_samples": (
                    len(sample_results) / sampled["requested_count"]
                ),
            },
            "samples": sample_results,
            "aggregation": {
                "method": "unvalidated_arithmetic_mean",
                "mean_score": mean_score,
                "maximum_score": max_score,
                "threshold": None,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "runtime_ms": round((time.perf_counter() - started) * 1000),
            "environment": {
                package: version(package) for package in ("torch", "torchvision", "Pillow")
            },
            "threshold": None,
            "preprocessing_version": "ffprobe-pts-nearest-v1+ufd-center-crop-224-clip-normalize-v1",
        }
        destination = ROOT / "data" / "runs"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"{run_id}.json").write_text(
            json.dumps(response, indent=2), encoding="utf-8"
        )
        return response
    finally:
        if sampled:
            for frame in sampled.get("frames", []):
                frame["image"].close()
        file.file.close()
        SLOTS.release()


@app.post("/api/d1/face-score-stability")
def face_score_stability(file: UploadFile = File(...), comparison: UploadFile | None = File(None)):
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(503, "Another scan is running. Try again shortly.")
    try:
        raw, image = _decode_image_upload(file)
        if image.width * image.height > 24_000_000:
            raise HTTPException(413, "Score stability supports images up to 24 megapixels.")
        copy_raw, copy_image = _decode_image_upload(comparison) if comparison else (None, None)
        if copy_image is not None:
            if copy_image.width * copy_image.height > 24_000_000:
                raise HTTPException(413, "Score stability supports images up to 24 megapixels.")
            aspect_ratio_change = abs(copy_image.width * image.height / (copy_image.height * image.width) - 1)
            if aspect_ratio_change > 0.02:
                raise HTTPException(422, "Choose a comparison copy with the same framing and aspect ratio.")
        try:
            result = compare_face_scores(image, face_forgery_detector, copy_image)
        except (ImportError, FileNotFoundError, OSError, ValueError, KeyError):
            raise HTTPException(503, "SBI could not score this comparison. Check the model setup.")
        return {"sha256": hashlib.sha256(raw).hexdigest(),
                "comparison_sha256": hashlib.sha256(copy_raw).hexdigest() if copy_raw else None,
                **result}
    finally:
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
                "Local SBI pilot or required base weights are unavailable."
                if face_forgery_detector.use_pilot else
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
            observation = f"Examined {prediction['face_count']} detected face(s)."
            if face_forgery_detector.use_still_images:
                observation += " Still-image pilot measured 79.27% accuracy on 685 scored test images; 315 other test images were unscored."
            else:
                observation += " Face-swap research pilot; performance depends on the dataset."

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
                "method": face_forgery_detector.model_id,
                "method_version": face_forgery_detector.model_version,
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
                "limitations": [
                    *FACE_LIMITATIONS,
                    *(["Fine-tuned on cleaned still-image face crops; test coverage was 68.5%. Multi-face maximum-score decisions were not evaluated.",
                       "Related identities across splits remain unverified, and the test sample was reused for model comparisons."]
                      if face_forgery_detector.use_still_images else
                      ["Fine-tuned on Celeb-DF v2 and DeepfakeTIMIT; benchmark results apply to the tested face swaps."]
                      if face_forgery_detector.use_pilot else []),
                ],
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


@app.post("/api/d1/scan")
def scan_evidence(
    file: UploadFile = File(...),
    evidence_id: str = Form(..., min_length=1, max_length=128),
    media_type: Literal["image", "audio"] = Form(...),
    requested_checks: set[str] | None = None,
):
    """Run the applicable model and file inspection, retaining independent outcomes."""
    limit = MAX_BYTES if media_type == "image" else MAX_AUDIO_BYTES
    try:
        raw = file.file.read(limit + 1)
    finally:
        file.file.close()
    if not raw:
        raise HTTPException(400, "Empty evidence file")
    if len(raw) > limit:
        raise HTTPException(413, "Evidence exceeds the scan size limit")

    run_id = "RUN-" + uuid.uuid4().hex
    requested = requested_checks or ({"image_model", "face_forgery", "file_inspection"}
                                     if media_type == "image" else {"audio_model", "file_inspection"})

    def finding(method, method_version, observation, **fields):
        return {
            "schema_version": "1.1", "finding_id": "F-" + uuid.uuid4().hex,
            "evidence_id": evidence_id, "run_id": run_id, "fixture": False,
            "category": "synthetic_media", "execution_status": "completed",
            "result": "inconclusive", "scope": "Submitted file", "score": None,
            "location": None, "support_refs": [], "limitations": [],
            "review_status": "unreviewed", "method": method,
            "method_version": method_version, "observation": observation,
            **fields,
        }

    def model_check():
        upload = UploadFile(io.BytesIO(raw), filename=file.filename)
        method, revision = (MODEL_ID, REVISION) if media_type == "image" else ("clovaai/AASIST", AUDIO_REVISION)
        try:
            if media_type == "image":
                result = analyze_image(upload)["finding"]
                return {**result, "evidence_id": evidence_id, "run_id": run_id}
            result = probe_audio(upload)
            end_ms = min(result["output"]["decoded"]["decoded_duration_ms"], 4038)
            return finding(
                method, revision, result["observation"],
                scope="Opening audio segment, up to 4.04 seconds",
                location={"kind": "time_range", "start_ms": 0, "end_ms": end_ms},
                score={"value": result["output"]["model"]["spoof_score"], "range": [0, 1],
                       "positive_class": "Spoofed speech", "interpretation": "Raw AASIST spoof score",
                       "calibration_status": "Uncalibrated"},
                limitations=result["limitations"],
            )
        except HTTPException as exc:
            return finding(method, revision, str(exc.detail), result=None,
                           execution_status="unsupported" if exc.status_code == 503 else "failed",
                           limitations=["No model assessment was produced."])
        except Exception:
            return finding(method, revision, "Model execution failed.", result=None,
                           execution_status="failed", limitations=["No model assessment was produced."])
        finally:
            upload.file.close()

    def face_check():
        upload = UploadFile(io.BytesIO(raw), filename=file.filename)
        try:
            result = analyze_face_forgery(upload)
            record = {**result["finding"], "evidence_id": evidence_id, "run_id": run_id}
            if record["execution_status"] == "no_face":
                record["execution_status"] = "completed"
            analysis = {
                **result["model"],
                "width": result["input"]["width"],
                "height": result["input"]["height"],
                "finding_id": record["finding_id"],
            }
            return record, analysis
        except HTTPException as exc:
            return finding(
                face_forgery_detector.model_id, face_forgery_detector.model_version, str(exc.detail), result=None,
                execution_status="unsupported" if exc.status_code == 503 else "failed",
                limitations=["No face-forgery assessment was produced."],
            ), None
        except Exception:
            return finding(
                face_forgery_detector.model_id, face_forgery_detector.model_version, "Face-forgery execution failed.", result=None,
                execution_status="failed", limitations=["No face-forgery assessment was produced."],
            ), None
        finally:
            upload.file.close()

    def detector_checks():
        # Both model endpoints use the same bounded inference slot.
        model_name = "image_model" if media_type == "image" else "audio_model"
        records = [model_check()] if model_name in requested else []
        face_analysis = None
        if media_type == "image" and "face_forgery" in requested:
            face_record, face_analysis = face_check()
            records.append(face_record)
        return records, face_analysis

    def file_check():
        try:
            if media_type == "image":
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(raw)) as image:
                        image_format, width, height = image.format, image.width, image.height
                        tables = len(getattr(image, "quantization", {}) or {})
                observation = f"Detected {image_format} header, {width} × {height} pixels."
                if image_format == "JPEG":
                    observation += f" Found {tables} JPEG quantization table(s)."
            else:
                from audio_probe import decode_audio
                _, metadata = decode_audio(raw)
                observation = f"Decoded {metadata['decoded_duration_ms']} ms as mono audio at {metadata['sample_rate_hz']} Hz."
            return finding("File inspection", "1.0", observation, category="tampering",
                           scope="Image container header" if media_type == "image" else "Bounded audio decode",
                           limitations=["File properties alone do not establish whether content was manipulated."])
        except Exception:
            return finding("File inspection", "1.0", "File properties could not be read.",
                           category="tampering", execution_status="failed", result=None,
                           limitations=["No file inspection result was produced."])

    with ThreadPoolExecutor(max_workers=2) as pool:
        model = pool.submit(detector_checks)
        metadata = pool.submit(file_check) if "file_inspection" in requested else None
        findings, face_analysis = model.result()
        if metadata is not None:
            findings.append(metadata.result())
    completed = sum(item["execution_status"] == "completed" for item in findings)
    return {
        "run_id": run_id, "evidence_id": evidence_id,
        "sha256": hashlib.sha256(raw).hexdigest(), "findings": findings,
        **({"face_analysis": face_analysis} if face_analysis is not None else {}),
        "summary": {
            "result": "inconclusive" if completed else "unavailable",
            "completed_checks": completed, "total_checks": len(findings),
            "reason": "The checks have different scopes. No validated fusion rule or combined confidence is available.",
        },
    }


run_repository = RunRepository(case_repository.database_path)
app.include_router(create_briefing_router(case_repository, runs=run_repository, provenance=latest_case_analysis))
app.include_router(create_reports_router(case_repository, run_repository, D2ReportArtifacts(d2_services, case_repository)))
run_repository.backfill_review_findings()


def _e2e_stub_finding(run: dict, check: str, index: int) -> dict:
    category = "tampering" if check == "file_inspection" else "synthetic_media"
    location = None
    if run["modality"] == "image":
        location = {"kind": "region", "x": 0.2, "y": 0.2, "width": 0.35, "height": 0.35,
                    "coordinate_space": "normalized", "label": "deterministic test region"}
    elif run["modality"] in {"audio", "video"}:
        location = {"kind": "time_range", "start_ms": index * 1000, "end_ms": index * 1000 + 750}
    return {
        "schema_version": "1.1", "finding_id": f"F-{run['run_id'][4:]}-{index}",
        "run_id": run["run_id"], "evidence_id": run["evidence_id"], "category": category,
        "execution_status": "completed", "result": "inconclusive",
        "observation": f"Deterministic test observation for {check}.",
        "method": "D4 deterministic test worker", "method_version": "1.0-test",
        "scope": "Committed E2E fixture", "score": None, "location": location,
        "support_refs": [],
        "limitations": ["Test-only deterministic output; no detector or scoring logic ran."],
        "review_status": "unreviewed", "error": None, "details": None, "fixture": False,
    }


def _e2e_stub_worker(run_id: str) -> None:
    run = run_repository.get_run(run_id)
    evidence = run_repository.resolve_evidence(run["evidence_id"], run["case_id"])
    scenario = evidence["filename"].lower()
    checks = list(run["requested_checks"])
    for check in checks:
        run_repository.append_event(run_id, check, "check.started", "running")
    for index, check in enumerate(checks):
        should_fail = ("failed" in scenario) or ("partial" in scenario and run["attempt"] == 1 and index == len(checks) - 1)
        if should_fail:
            run_repository.append_event(run_id, check, "check.failed", "failed", {
                "error": {"code": "E2E_DETERMINISTIC_FAILURE", "message": f"Deterministic failure for {check}.", "retryable": True}
            })
            continue
        finding = _e2e_stub_finding(run, check, index)
        payload: dict = {"findings": [finding]}
        if run["modality"] == "video":
            payload["coverage"] = {
                "planned": 3, "examined": 2, "rejected": 0, "unexamined": 1,
                "percent": 66.67, "duration_ms": 3000, "strategy": "deterministic e2e samples",
                "sampling_interval_ms": 1000,
                "samples": [
                    {"index": 0, "timestamp_ms": 0, "status": "examined", "reason": None},
                    {"index": 1, "timestamp_ms": 1000, "status": "examined", "reason": None},
                    {"index": 2, "timestamp_ms": 2000, "status": "unexamined", "reason": "deterministic test gap"},
                ],
            }
        run_repository.append_event(run_id, check, "check.completed", "completed", payload)


def _persistent_run_worker(run_id: str) -> None:
    if E2E_STUB_ENABLED:
        _e2e_stub_worker(run_id)
        return
    run = run_repository.get_run(run_id)
    path = run_repository.input_path(run_id)
    checks = list(run["requested_checks"])
    for check in checks:
        run_repository.append_event(run_id, check, "check.started", "running")
    if path is None or not path.is_file():
        for check in checks:
            run_repository.append_event(run_id, check, "check.failed", "failed", {
                "error": {"code": "INPUT_NOT_AVAILABLE", "message": "The persisted analysis copy is unavailable.", "retryable": True}
            })
        return
    try:
        raw = path.read_bytes()
        evidence = run_repository.resolve_evidence(run["evidence_id"], run["case_id"])
        if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
            raise ValueError("Stored analysis input failed SHA-256 verification")
        if run["modality"] == "video":
            result = analyze_video(UploadFile(io.BytesIO(raw), filename=evidence["filename"]))
            mapped = map_video_response(result, run_id, run["evidence_id"])
            event_status = "unexamined" if mapped["coverage"]["unexamined"] else "completed"
            run_repository.append_event(
                run_id, "video_frame_analysis", "check.partial" if event_status == "unexamined" else "check.completed",
                event_status, mapped,
            )
            return

        result = scan_evidence(
            UploadFile(io.BytesIO(raw), filename=evidence["filename"]),
            run["evidence_id"], run["modality"], set(checks),
        )
        grouped: dict[str, list[dict]] = {check: [] for check in checks}
        for finding in result["findings"]:
            if finding.get("method") == face_forgery_detector.model_id:
                check = "face_forgery"
            elif finding.get("category") == "tampering":
                check = "file_inspection"
            else:
                check = "image_model" if run["modality"] == "image" else "audio_model"
            if check in grouped:
                grouped[check].append({**finding, "run_id": run_id, "evidence_id": run["evidence_id"]})
        for check in checks:
            findings = grouped.get(check, [])
            failed = next((item for item in findings if item.get("execution_status") in {"failed", "unsupported"}), None)
            if failed or not findings:
                message = failed.get("observation", "The check produced no result.") if failed else "The check produced no result."
                run_repository.append_event(run_id, check, "check.failed", "failed", {
                    "findings": findings,
                    "error": {"code": "CHECK_FAILED", "message": message, "retryable": True},
                })
            else:
                run_repository.append_event(run_id, check, "check.completed", "completed", {"findings": findings})
    except HTTPException as error:
        for check in checks:
            latest = run_repository.get_run(run_id)
            states = {event["check"]: event["status"] for event in latest["events"]}
            if states.get(check) == "running":
                run_repository.append_event(run_id, check, "check.failed", "failed", {
                    "error": {"code": f"HTTP_{error.status_code}", "message": str(error.detail),
                              "retryable": error.status_code >= 429},
                })
    except Exception:
        for check in checks:
            latest = run_repository.get_run(run_id)
            states = {event["check"]: event["status"] for event in latest["events"]}
            if states.get(check) == "running":
                run_repository.append_event(run_id, check, "check.failed", "failed", {
                    "error": {"code": "CHECK_EXCEPTION", "message": "The analysis check failed unexpectedly.", "retryable": True},
                })


run_repository.recover_stale_runs()
run_scheduler = RunScheduler(_persistent_run_worker)
app.include_router(
    create_runs_router(run_repository, run_scheduler, ROOT / "data" / "evidence"),
    prefix="/api",
)

case_automation = CaseAutomation(
    case_repository, run_repository, _persistent_run_worker,
    lambda job, item, evidence, raw: authenticate_zip_item(case_repository, job, item, evidence, raw),
    lambda job, items: relate_zip_items(case_repository, job, items),
)
app.include_router(create_automation_router(case_automation), prefix="/api")
