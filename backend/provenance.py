"""Image relationship analysis for local investigative comparison."""
from __future__ import annotations

import hashlib
import io
import json
from importlib.metadata import version
import re
import platform
import uuid
import warnings
from datetime import datetime, timezone
from threading import BoundedSemaphore

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field
from provenance_tools import recorded_metadata, metadata_flags, credentials, inspect_audio
from provenance_store import ProvenanceStore
from provenance_pair_planner import plan_comparisons
from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

router = APIRouter(prefix="/api/d1/provenance", tags=["Provenance"])
COMPARISON_SLOT = BoundedSemaphore(1)
MAX_FILES = 12
MAX_BYTES = 15 * 1024 * 1024
MAX_TOTAL_BYTES = 60 * 1024 * 1024
MAX_PIXELS = 20_000_000
FORMATS = {"JPEG", "PNG", "WEBP"}
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    FORMATS.add("HEIF")
except ImportError:
    pass
METADATA_FIELDS = {
    "Make", "Model", "Software", "DateTime", "DateTimeOriginal", "DateTimeDigitized",
    "Artist", "Copyright", "LensModel", "ImageDescription", "Orientation",
}


def validate_preview_image(image):
    if (image.format not in FORMATS or image.width * image.height > MAX_PIXELS
            or getattr(image, "is_animated", False)):
        raise ValueError("Use static JPEG, PNG, WebP or supported HEIC images up to 20 megapixels.")


def oriented_preview(image):
    preview = ImageOps.exif_transpose(image).convert("RGB")
    preview.thumbnail((1200, 1200))
    return preview


def jpeg_preview_response(preview):
    stream = io.BytesIO()
    preview.save(stream, format="JPEG", quality=88)
    return Response(stream.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/preview")
def preview_upload(file: UploadFile = File(...)):
    """Decode a temporary preview before intake without saving the uploaded file."""
    try:
        raw = file.file.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 15 MiB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                validate_preview_image(image)
                return jpeg_preview_response(oriented_preview(image))
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise HTTPException(400, "Unable to preview this image. Use a supported static image up to 20 megapixels.") from error
    finally:
        file.file.close()


def inspect_image(raw: bytes, filename: str, image_id: str):
    """Return a public record and bounded, oriented pixels for comparison."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                validate_preview_image(image)
                image.load()
                metadata = {}
                exif = image.getexif()
                # EXIF date and camera fields can reside in the nested Exif IFD.
                tags = dict(exif)
                try:
                    tags.update(exif.get_ifd(0x8769))
                except (KeyError, ValueError, TypeError):
                    pass
                for key, value in tags.items():
                    name = ExifTags.TAGS.get(key, str(key))
                    if name in METADATA_FIELDS:
                        metadata[name] = str(value)[:400]
                for key in ("Software", "Description", "Author", "Copyright", "Creation Time"):
                    if key in image.info:
                        metadata[key] = str(image.info[key])[:400]
                extracted, metadata_method = recorded_metadata(raw)
                metadata.update(extracted)
                record = {
                    "id": image_id, "media_type": "image",
                    "filename": filename.replace("\\", "/").rsplit("/", 1)[-1][:255],
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw), "format": image.format,
                    "width": image.width, "height": image.height,
                    "metadata": metadata,
                    "source_observation": (
                        "Recorded camera information is available in this file."
                        if metadata.get("Make") or metadata.get("Model") else
                        "The file provides no readable camera make or model."
                    ),
                    "metadata_status": "Information recorded in the file; origin and timestamps are unverified.",
                    "metadata_method": metadata_method,
                    "metadata_flags": metadata_flags(metadata),
                    "content_credentials": credentials(raw, image.format),
                    "detector_signals": [],
                }
                return record, oriented_preview(image)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise ValueError("Unable to read a supported static image.") from error


def comparison_box(size, area):
    width, height = size
    if area is None:
        return (0, 0, width, height)
    return tuple(round(fraction * dimension) for fraction, dimension in zip(area, (width, height, width, height)))


def parse_comparison_areas(raw, count):
    if raw is None:
        return [None] * count
    areas = json.loads(raw)
    if not isinstance(areas, list) or len(areas) != count:
        raise ValueError("Provide one comparison area or null per uploaded file.")
    for area in areas:
        if area is None:
            continue
        if (not isinstance(area, list) or len(area) != 4
                or any(type(value) not in (int, float) or not 0 <= value <= 1 for value in area)
                or not (area[0] < area[2] and area[1] < area[3])):
            raise ValueError("Comparison areas must be ordered rectangles within the image.")
    return areas


def prepare_visual(image, area=None):
    if image is None:
        return None
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    x0, y0, x1, y1 = comparison_box(image.size, area)
    if area is not None and min(x1 - x0, y1 - y0) < 32:
        raise ValueError("Select a larger photo area (at least 32 pixels on each side at analysis resolution).")
    selected = gray[y0:y1, x0:x1]
    keypoints, descriptors = cv2.SIFT_create(nfeatures=3500).detectAndCompute(selected, None)
    if x0 or y0:
        for point in keypoints:
            point.pt = (point.pt[0] + x0, point.pt[1] + y0)
    thumb = cv2.resize(selected, (9, 8), interpolation=cv2.INTER_AREA)
    dhash = int.from_bytes(np.packbits(thumb[:, 1:] > thumb[:, :-1]).tobytes(), "big")
    return {"gray": gray, "rgb": np.asarray(image), "keypoints": keypoints,
            "descriptors": descriptors, "dhash": dhash, "comparison_size": (x1-x0, y1-y0)}


def compare_visual(left, right):
    """Require spatially distributed feature matches consistent with one geometry."""
    import cv2
    if left is None or right is None:
        return None
    if left["descriptors"] is None or right["descriptors"] is None:
        return None
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(left["descriptors"], right["descriptors"], k=2)
    candidates = [a for pair in pairs if len(pair) == 2
                  for a, b in [pair] if a.distance < 0.72 * b.distance]
    # One-to-one target points prevent repeated texture from inflating support.
    candidates = sorted(candidates, key=lambda match: match.distance)
    unique = {}
    for match in candidates:
        unique.setdefault(match.trainIdx, match)
    return verify_visual_matches(left, right, [(m.queryIdx, m.trainIdx) for m in unique.values()])


def verify_visual_matches(left, right, matches, method="SIFT descriptors, L2 ratio test and RANSAC homography"):
    """Apply the same geometric checks to proposed keypoint pairs."""
    import cv2
    import numpy as np

    if len(matches) < 16:
        return None
    source = np.float32([left["keypoints"][i].pt for i, _ in matches])
    target = np.float32([right["keypoints"][j].pt for _, j in matches])
    homography, mask = cv2.findHomography(source, target, cv2.RANSAC, 4.0)
    if homography is None or mask is None or not np.isfinite(homography).all():
        return None
    inliers = mask.ravel().astype(bool)
    count = int(inliers.sum())
    ratio = count / len(matches)
    if count < 16 or ratio < .45:
        return None

    def coverage(points, visual):
        width, height = visual["comparison_size"]
        agreed = points[inliers]
        if np.any(np.ptp(agreed, axis=0) < np.array([width, height]) * .12):
            return 0.0
        return float(cv2.contourArea(cv2.convexHull(agreed)) / (width * height))

    left_coverage = coverage(source, left)
    right_coverage = coverage(target, right)
    if min(left_coverage, right_coverage) < .015 or max(left_coverage, right_coverage) < .05:
        return None

    def bounds(points, gray):
        selected = points[inliers]
        minimum, maximum = selected.min(0), selected.max(0)
        return [round(float(minimum[0] / gray.shape[1]), 4),
                round(float(minimum[1] / gray.shape[0]), 4),
                round(float(maximum[0] / gray.shape[1]), 4),
                round(float(maximum[1] / gray.shape[0]), 4)]

    # Sample actual inliers across the extent of the match for the viewer.
    agreed_left, agreed_right = source[inliers], target[inliers]
    order = np.lexsort((agreed_left[:, 0], agreed_left[:, 1]))
    displayed = order[np.linspace(0, count - 1, min(count, 100), dtype=int)]
    left_scale = np.array(left["gray"].shape[::-1])
    right_scale = np.array(right["gray"].shape[::-1])
    return {
        "point_pairs": np.round(np.column_stack((
            agreed_left[displayed] / left_scale, agreed_right[displayed] / right_scale,
        )), 5).tolist(),
        "matched_features": count, "candidate_features": len(matches),
        "geometric_inlier_ratio": round(ratio, 4),
        "left_coverage": round(left_coverage, 4), "right_coverage": round(right_coverage, 4),
        "left_region": bounds(source, left["gray"]), "right_region": bounds(target, right["gray"]),
        "homography": homography.tolist(),
        "left_size": [left["gray"].shape[1], left["gray"].shape[0]],
        "right_size": [right["gray"].shape[1], right["gray"].shape[0]],
        "method": method,
    }


def inspect_provenance_video(raw, name, image_id):
    from video_probe import VideoProbeError, VideoSampler

    try:
        sampled = VideoSampler().sample(raw, name, max_samples=4)
    except VideoProbeError as error:
        raise ValueError(f"{name}: {error.detail}") from error
    metadata = sampled["metadata"]
    record = {
        "id": image_id, "filename": name.replace(chr(92), "/").rsplit("/", 1)[-1][:255],
        "format": "MP4", "media_type": "video", "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(), "width": metadata["width"],
        "height": metadata["height"], "metadata": {key: str(value) for key, value in metadata.items()},
        "metadata_flags": [], "metadata_method": "ffprobe",
        "source_observation": "Video container and stream fields were read.",
        "metadata_status": "File-provided stream information.",
        "content_credentials": credentials(raw, "MP4"), "detector_signals": [],
        "video_coverage": {"duration_ms": metadata["duration_ms"],
                           "source_frame_timestamps": metadata["source_frame_timestamps"],
                           "requested_count": sampled["requested_count"],
                           "examined_timestamps_ms": [frame["timestamp_ms"] for frame in sampled["frames"]],
                           "rejected": sampled["rejected"]},
    }
    frames = []
    for frame in sampled["frames"]:
        image = frame["image"]
        image.thumbnail((900, 900))
        frames.append((frame["timestamp_ms"], prepare_visual(image)))
    return record, frames


def compare_video_frames(left, right):
    best = None
    for left_time, left_frame in left:
        for right_time, right_frame in right:
            match = compare_visual(left_frame, right_frame)
            if match and (best is None or match["matched_features"] > best["matched_features"]):
                best = {**match, "frame_timestamps_ms": [left_time, right_time],
                        "sample_pair_count": len(left) * len(right)}
    return best


def analyze_images(inputs, areas=None, pair_budget=None):
    if not 2 <= len(inputs) <= MAX_FILES:
        raise ValueError(f"Select between 2 and {MAX_FILES} images.")
    if any(not raw or len(raw) > MAX_BYTES for _, raw in inputs):
        raise ValueError("Each image must contain data and be at most 15 MiB.")
    if sum(len(raw) for _, raw in inputs) > MAX_TOTAL_BYTES:
        raise ValueError("The image batch exceeds 60 MiB.")
    if sum(name.lower().endswith(".mp4") for name, _ in inputs) > 4:
        raise ValueError("Compare up to four MP4 files per analysis.")
    records, visuals, video_frames = [], [], {}
    for index, (name, raw) in enumerate(inputs, 1):
        if name.lower().endswith(".mp4"):
            if areas is not None and areas[index - 1] is not None:
                raise ValueError("Photo areas can only be selected for images.")
            record, frames = inspect_provenance_video(raw, name, f"IMG-{index:02d}")
            video_frames[record["id"]] = frames
            image = None
        elif name.lower().endswith((".wav",".mp3")):
            record, image = inspect_audio(raw, name, f"IMG-{index:02d}")
        else:
            record, image = inspect_image(raw, name, f"IMG-{index:02d}")
        area = areas[index - 1] if areas is not None else None
        if area is not None:
            if image is None:
                raise ValueError("Photo areas can only be selected for images.")
            record["comparison_area"] = area
        visual = prepare_visual(image, area)
        record["dhash"] = f"{visual['dhash']:016x}" if visual else None
        records.append(record)
        visuals.append(visual)
    selected_pairs, pair_plan = plan_comparisons(records, visuals, video_frames, pair_budget)
    relationships = []
    compared = 0
    for left_index, left in enumerate(records):
        for right_index in range(left_index + 1, len(records)):
            compared += 1
            right = records[right_index]
            common = {"id": f"REL-{compared:03d}", "left_id": left["id"], "right_id": right["id"]}
            if left["sha256"] == right["sha256"]:
                relationships.append({
                    **common, "kind": "exact_copy", "support": None,
                    "explanation": "The SHA-256 hashes match. These files contain exactly the same bytes.",
                })
                continue
            if (left_index, right_index) not in selected_pairs:
                continue
            if left["id"] in video_frames and right["id"] in video_frames:
                support = compare_video_frames(video_frames[left["id"]], video_frames[right["id"]])
                if support:
                    relationships.append({
                        **common, "kind": "matching_content", "support": support,
                        "explanation": "The sampled frames share visual content. Only the examined timestamps support this link.",
                    })
                continue
            left_visual, right_visual = visuals[left_index], visuals[right_index]
            distance = (left_visual["dhash"] ^ right_visual["dhash"]).bit_count() if left_visual and right_visual else None
            support = compare_visual(left_visual, right_visual)
            if support:
                support["hash_distance"] = distance
                support["candidate_search"] = "dHash distance <= 10" if distance is not None and distance <= 10 else "Expanded region search for possible crops despite different global hashes"
                relationships.append({
                    **common, "kind": "matching_content", "support": support,
                    "explanation": (
                        f"Possible relation supported by {support['matched_features']} matching points. "
                        "Creation order and the specific edit operation remain unverified."
                    ),
                })
    for left_index, left in enumerate(records):
        for right in records[left_index + 1:]:
            agreed = {key: left["metadata"][key] for key in ("Make", "Model", "Software")
                      if left["metadata"].get(key) and left["metadata"].get(key) == right["metadata"].get(key)}
            if agreed:
                relationships.append({
                    "id": f"META-{left['id']}-{right['id']}", "left_id": left["id"], "right_id": right["id"],
                    "kind": "shared_metadata", "support": None, "metadata_fields": agreed,
                    "explanation": "These file-provided fields agree. This does not establish the same camera device, owner or editing history.",
                })
            left_manifests = left["content_credentials"].get("manifest_digests", {})
            right_manifests = right["content_credentials"].get("manifest_digests", {})
            labels = {label for label,value in left_manifests.items() if right_manifests.get(label)==value}
            if labels:
                relationships.append({
                    "id": f"C2PA-{left['id']}-{right['id']}", "left_id": left["id"], "right_id": right["id"],
                    "kind": "shared_credentials", "support": None, "manifest_labels": sorted(labels),
                    "explanation": "The embedded credential stores include matching manifest records. Review validation results for both files.",
                })
    duplicates = {}
    for image in records:
        duplicates.setdefault(image["sha256"], []).append(image["id"])
    try:
        import cv2
        visual_version = cv2.__version__
    except ImportError:
        visual_version = None
    return {
        "schema_version": "1.0", "analysis_id": "PROV-" + uuid.uuid4().hex,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "images": records, "relationships": relationships,
        "compared_pairs": compared, "pair_selection": pair_plan, "visual_matching_available": visual_version is not None,
        "exact_duplicate_groups": [group for group in duplicates.values() if len(group) > 1],
        "methods": {"hash": "SHA-256", "metadata": "ExifTool with Pillow image fallback; ffprobe for audio",
                    "visual": "dHash candidates; SIFT + RANSAC with expanded crop search" if visual_version else "unavailable",
                    "opencv_version": visual_version, "python_version": platform.python_version(),
                    "pillow_version": version("Pillow"), "credential_validator": "c2pa-python (offline)"},

        "limitations": [
            pair_plan["scope"], pair_plan["limitation"],
            "Connections describe matching content. They do not identify an original uploader or establish editing order.",
            "Visual comparison uses the investigator-selected photo area when provided; exact-copy and metadata checks still use whole files.",
            "A visual match can involve shared background or objects; it does not authenticate a face.",
            "No match means this method found insufficient support, rather than proving the files are unrelated.",
            "Metadata can be changed or stripped. Recorded device and software names are unverified claims.",
            "Credentials describe signed assertions. Signature validity, content binding and signer trust are reported separately.",
            "Video comparisons use up to four timestamped frames per MP4 (120 seconds maximum). Unsampled content and audio tracks are outside visual coverage.",
            "Recompression, screenshots and heavy edits can strip metadata and weaken matching.",
            "Difference overlays include alignment error, compression and lighting changes as well as possible edits.",
            "This report supports evidence-handling review. It provides no legal admissibility decision.",
        ],
    }


@router.post("/analyze")
def analyze_uploads(
    files: list[UploadFile] = File(...),
    case_id: str = Form("PROV-DEMO", min_length=1, max_length=100),
    case_title: str = Form("Media relationship examination", max_length=200),
    analyst: str = Form("Local analyst", min_length=1, max_length=100),
    comparison_areas: str | None = Form(None, max_length=2048),
    pair_budget: int | None = Form(None, ge=1, le=4950),
):
    acquired = COMPARISON_SLOT.acquire(blocking=False)
    try:
        if not acquired:
            raise HTTPException(429, "An image comparison is already running. Try again shortly.")
        if not 2 <= len(files) <= MAX_FILES:
            raise HTTPException(400, f"Select between 2 and {MAX_FILES} images.")
        inputs, total = [], 0
        for file in files:
            raw = file.file.read(MAX_BYTES + 1)
            total += len(raw)
            if len(raw) > MAX_BYTES or total > MAX_TOTAL_BYTES:
                raise HTTPException(413, "Use images up to 15 MiB each and 60 MiB per batch.")
            inputs.append((file.filename or "image", raw))
        if not case_id.strip() or not analyst.strip():
            raise HTTPException(400, "Case ID and analyst are required")
        report = analyze_images(inputs, parse_comparison_areas(comparison_areas, len(inputs)), pair_budget)
        return ProvenanceStore().save(report, inputs, case_id.strip(), analyst.strip(), case_title.strip())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    finally:
        if acquired:
            COMPARISON_SLOT.release()
        for file in files:
            file.file.close()


def saved_report(report_id):
    if not re.fullmatch(r"PROV-[a-f0-9]{32}", report_id):
        raise HTTPException(404, "Comparison report not found")
    try:
        return ProvenanceStore().get(report_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


class CaseComparison(BaseModel):
    evidence_ids: list[str] = Field(min_length=2, max_length=MAX_FILES)
    comparison_areas: list[list[float] | None] | None = None
    pair_budget: int | None = Field(default=None, ge=1, le=4950)


@router.post("/cases/{case_id}/analyze")
def analyze_case_originals(case_id: str, request: CaseComparison):
    from cases.router import get_case_repository

    acquired = COMPARISON_SLOT.acquire(blocking=False)
    if not acquired:
        raise HTTPException(429, "A comparison is already running.")
    try:
        repository = get_case_repository()
        case = repository.get_case(case_id)
        if not case:
            raise HTTPException(404, "Case not found")
        if len(set(request.evidence_ids)) != len(request.evidence_ids):
            raise ValueError("Select each case item once.")
        records = {item["evidence_id"]: item for item in repository.list_evidence(case_id) if item["preserved"]}
        if any(evidence_id not in records for evidence_id in request.evidence_ids):
            raise HTTPException(404, "A selected original is unavailable in this case")
        selected = [records[evidence_id] for evidence_id in request.evidence_ids]
        if sum(item["size_bytes"] for item in selected) > MAX_TOTAL_BYTES:
            raise HTTPException(413, "The selected originals exceed 60 MiB")
        store = ProvenanceStore()
        inputs = []
        for item in selected:
            path = store.blob_path(item["sha256"])
            raw = path.read_bytes() if path.is_file() else b""
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise HTTPException(409, "Preserved case original failed SHA-256 verification")
            inputs.append((item["filename"], raw))
        areas = parse_comparison_areas(
            json.dumps(request.comparison_areas) if request.comparison_areas is not None else None, len(inputs))
        report = analyze_images(inputs, areas, request.pair_budget)
        for image, item in zip(report["images"], selected):
            image["case_evidence_id"] = item["evidence_id"]
            image["case_intake"] = {"registered_at": item["registered_at"], "registered_by": item["registered_by"],
                                    "registered_by_verified": False, "receipt": item.get("receipt")}
        return store.save(report, inputs, case_id, "Local analyst", case["title"])
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    finally:
        COMPARISON_SLOT.release()


@router.get("/cases/{case_id}/latest")
def latest_case_analysis(case_id: str):
    for item in report_history(case_id):
        report = saved_report(item["id"])
        if any(image.get("case_evidence_id") for image in report["images"]):
            return report
    return None


@router.get("/reports")
def report_history(case_id: str):
    store = ProvenanceStore()
    db = store.connect()
    try:
        rows = db.execute("SELECT id,created_at,body_hash FROM provenance_reports WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.get("/reports/{report_id}")
def read_saved_report(report_id: str):
    return saved_report(report_id)


@router.get("/reports/{report_id}/images/{image_id}")
def read_original(report_id: str, image_id: str):
    report = saved_report(report_id)
    image = next((item for item in report["images"] if item["id"] == image_id), None)
    if not image:
        raise HTTPException(404, "Image not found")
    path = ProvenanceStore().blob_path(image["sha256"])
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != image["sha256"]:
        raise HTTPException(409, "Preserved original failed hash verification")
    return FileResponse(path, media_type={"JPEG":"image/jpeg", "PNG":"image/png", "WEBP":"image/webp","WAV":"audio/wav","MP3":"audio/mpeg","HEIF":"image/heic","MP4":"video/mp4"}[image["format"]])


@router.get("/reports/{report_id}/audit")
def read_provenance_audit(report_id: str):
    report = saved_report(report_id)
    return {"entries": ProvenanceStore().events(report["case"]["id"]),
            "scope": report["integrity"]["log_scope"], "limitations": report["integrity"]["limitations"]}


@router.post("/reports/{report_id}/verify")
def verify_preserved(report_id: str, retained_anchor: str | None = None):
    if retained_anchor is not None and not re.fullmatch("[a-f0-9]{64}", retained_anchor):
        raise HTTPException(400, "Expected anchor must be a SHA-256 hash")
    report = saved_report(report_id)
    return ProvenanceStore().verify(report, retained_anchor)


@router.post("/reports/{report_id}/images/{image_id}/verify")
def verify_supplied_image(report_id: str, image_id: str, file: UploadFile = File(...)):
    try:
        report = saved_report(report_id)
        image = next((item for item in report["images"] if item["id"] == image_id), None)
        if not image:
            raise HTTPException(404, "Image not found")
        digest = hashlib.sha256()
        total = 0
        while chunk := file.file.read(256 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                raise HTTPException(413, "Image exceeds 15 MiB")
            digest.update(chunk)
        actual = digest.hexdigest()
        return {"expected": image["sha256"], "actual": actual, "matches": actual == image["sha256"]}
    finally:
        file.file.close()


def difference_image(report, relationship):
    import cv2
    import numpy as np
    store = ProvenanceStore()
    images, masks = [], []
    for image_id in (relationship["left_id"], relationship["right_id"]):
        item = next(item for item in report["images"] if item["id"] == image_id)
        raw = store.blob_path(item["sha256"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Preserved original failed hash verification")
        with Image.open(io.BytesIO(raw)) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((1200, 1200))
        images.append(np.asarray(image))
        x0, y0, x1, y1 = comparison_box(image.size, item.get("comparison_area"))
        mask = np.zeros((image.height, image.width), dtype=np.uint8)
        mask[y0:y1, x0:x1] = 1
        masks.append(mask)
    left, right = images
    height, width = right.shape[:2]
    transform = np.array(relationship["support"]["homography"])
    aligned = cv2.warpPerspective(left, transform, (width, height))
    valid = cv2.warpPerspective(masks[0], transform,
                                (width, height), flags=cv2.INTER_NEAREST)
    valid = (cv2.erode(valid, np.ones((9,9), dtype=np.uint8)) > 0) & (masks[1] > 0)
    delta = cv2.GaussianBlur(cv2.absdiff(aligned, right).mean(axis=2).astype(np.float32), (5,5), 0)
    changed = (delta > 30) & valid
    overlay = right.copy()
    overlay[changed] = (right[changed] * .45 + np.array([230, 65, 55]) * .55).astype(np.uint8)
    stream = io.BytesIO()
    Image.fromarray(overlay).save(stream, format="PNG")
    percent = float(changed.sum() / max(1, valid.sum()) * 100)
    return stream.getvalue(), percent


@router.get("/reports/{report_id}/relationships/{relationship_id}/difference")
def aligned_difference(report_id: str, relationship_id: str):
    report = saved_report(report_id)
    edge = next((item for item in report["relationships"] if item["id"] == relationship_id), None)
    if not edge or not edge["support"] or edge["support"].get("frame_timestamps_ms"):
        raise HTTPException(400, "Select a geometric image match for a difference overlay")
    try:
        raw, percent = difference_image(report, edge)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return Response(raw, media_type="image/png", headers={"X-Changed-Overlap-Percent": f"{percent:.2f}"})


@router.post("/reports/{report_id}/pdf")
def generate_pdf(report_id: str):
    from provenance_pdf import build_pdf
    report = saved_report(report_id)
    store = ProvenanceStore()
    verification = store.verify(report)
    if not verification["chain_valid"] or not verification["anchor_matches"] or not verification["all_originals_match"]:
        raise HTTPException(409, "Resolve integrity verification failures before generating a report")
    store.log_action(report,"report_generation_requested",{"analysis_id":report_id,"report_sha256":report["report_sha256"]})
    raw = build_pdf(report,store.events(report["case"]["id"]),store,difference_image)
    pdf_hash = hashlib.sha256(raw).hexdigest()
    store.log_action(report,"pdf_generated",{"analysis_id":report_id,"pdf_sha256":pdf_hash})
    return Response(raw,media_type="application/pdf",headers={
        "Content-Disposition":f'attachment; filename="{report_id}.pdf"',
        "X-PDF-SHA256":pdf_hash,"X-Report-SHA256":report["report_sha256"],
    })


@router.post("/reports/{report_id}/images/{image_id}/signals")
def supporting_signals(report_id: str, image_id: str):
    from main import scan_evidence
    report = saved_report(report_id)
    image = next((item for item in report["images"] if item["id"]==image_id),None)
    if not image:
        raise HTTPException(404,"Image not found")
    if image.get("media_type") == "video":
        raise HTTPException(400, "Run video detection from the case evidence workbench.")
    raw = ProvenanceStore().blob_path(image["sha256"]).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=image["sha256"]:
        raise HTTPException(409,"Preserved original failed verification")
    result = scan_evidence(UploadFile(io.BytesIO(raw),filename=image["filename"]),
                           evidence_id=image_id,media_type=image.get("media_type","image"))
    signals = [finding for finding in result["findings"] if finding.get("method") != "File inspection"]
    return ProvenanceStore().revision(report,image_id,signals)


@router.get("/reports/{report_id}/export")
def export_saved_report(report_id: str):
    report = saved_report(report_id)
    # Preserve server numeric representation so recomputing the documented
    # sorted-key payload hash does not turn 1.0 into 1 during browser serialization.
    raw = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
    return Response(raw, media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="{report_id}.json"',
        "X-Report-SHA256": report["report_sha256"],
    })


@router.get("/reports/{report_id}/images/{image_id}/preview")
def image_preview(report_id: str, image_id: str):
    report = saved_report(report_id)
    image = next((item for item in report["images"] if item["id"] == image_id), None)
    if not image or image.get("media_type", "image") != "image":
        raise HTTPException(404, "Image preview unavailable")
    raw = ProvenanceStore().blob_path(image["sha256"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != image["sha256"]:
        raise HTTPException(409, "Preserved original failed hash verification")
    # Intake already validated the content. Rendering a thumbnail must not rerun
    # ExifTool and credential verification for every browser image request.
    with Image.open(io.BytesIO(raw)) as original:
        return jpeg_preview_response(oriented_preview(original))


class ReviewNote(BaseModel):
    author: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=4000)
    scope_id: str | None = Field(default=None, max_length=80)


@router.post("/reports/{report_id}/notes")
def add_review_note(report_id: str, note: ReviewNote):
    report = saved_report(report_id)
    if not note.author.strip() or not note.text.strip():
        raise HTTPException(400, "Reviewer and note are required")
    allowed = {item["id"] for item in report["images"] + report["relationships"]}
    if note.scope_id and note.scope_id not in allowed:
        raise HTTPException(400, "Select a file or connection from this analysis")
    store = ProvenanceStore()
    checked = store.verify(report)
    if not all(checked[key] for key in ("chain_valid", "anchor_matches", "all_originals_match")):
        raise HTTPException(409, "Resolve integrity failures before recording a review")
    record = {"author": note.author.strip(), "text": note.text.strip(), "scope_id": note.scope_id,
              "timestamp": datetime.now(timezone.utc).isoformat(), "identity": "Self-declared reviewer",
              "classification": "Reviewer interpretation; not an automated finding", "analysis_id": report_id}
    return store.revision(report, review=record)


@router.post("/reports/{report_id}/extend")
def extend_analysis(
    report_id: str, files: list[UploadFile] = File(...),
    comparison_areas: str | None = Form(None, max_length=2048),
):
    acquired = COMPARISON_SLOT.acquire(blocking=False)
    try:
        if not acquired:
            raise HTTPException(429, "A comparison is already running. Try again shortly.")
        parent = saved_report(report_id)
        if not files or len(parent["images"]) + len(files) > MAX_FILES:
            raise HTTPException(400, "The expanded analysis must contain at most 12 files")
        store = ProvenanceStore()
        checked = store.verify(parent)
        if not all(checked[key] for key in ("chain_valid", "anchor_matches", "all_originals_match")):
            raise HTTPException(409, "Resolve integrity failures before adding files")
        inputs = [(item["filename"], store.blob_path(item["sha256"]).read_bytes()) for item in parent["images"]]
        total = sum(len(raw) for _, raw in inputs)
        for file in files:
            raw = file.file.read(MAX_BYTES + 1)
            total += len(raw)
            if not raw or len(raw) > MAX_BYTES or total > MAX_TOTAL_BYTES:
                raise HTTPException(413, "Use nonempty files up to 15 MiB each and 60 MiB per analysis")
            inputs.append((file.filename or "media", raw))
        areas = [item.get("comparison_area") for item in parent["images"]]
        areas.extend(parse_comparison_areas(comparison_areas, len(files)))
        report = analyze_images(inputs, areas)
        report["parent_analysis_id"] = parent["analysis_id"]
        report["review_notes"] = parent.get("review_notes", [])
        # Existing file IDs remain stable; pair-scoped notes retain their original analysis reference.
        for note in report["review_notes"]:
            note.setdefault("analysis_id", parent["analysis_id"])
        for image, previous in zip(report["images"], parent["images"]):
            image["detector_signals"] = previous.get("detector_signals", [])
            if previous.get("case_evidence_id"):
                image["case_evidence_id"] = previous["case_evidence_id"]
                if previous.get("case_intake"):
                    image["case_intake"] = previous["case_intake"]
        return store.save(report, inputs, parent["case"]["id"], parent["case"]["analyst"], parent["case"]["title"])
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    finally:
        if acquired:
            COMPARISON_SLOT.release()
        for file in files:
            file.file.close()


@router.post("/reports/{report_id}/bundle")
def evidence_bundle(report_id: str):
    """Portable originals, report, chained activity and standalone offline verifier."""
    import zipfile
    from pathlib import Path
    from provenance_store import digest
    from provenance_pdf import build_pdf
    report = saved_report(report_id)
    store = ProvenanceStore()
    checked = store.verify(report)
    if not all(checked[key] for key in ("chain_valid", "anchor_matches", "all_originals_match")):
        raise HTTPException(409, "Resolve integrity failures before exporting an evidence package")
    store.log_action(report, "evidence_package_requested", {"analysis_id": report_id, "report_sha256": report["report_sha256"]})
    events = store.events(report["case"]["id"])
    payload = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False).encode()
    pdf = build_pdf(report, events, store, difference_image)
    contents = {"report.json": payload, "report.pdf": pdf,
                "activity.json": json.dumps(events, ensure_ascii=False, indent=2).encode(),
                "verify.py": (Path(__file__).parent / "verify_provenance_package.py").read_bytes()}
    for item in report["images"]:
        contents["originals/" + item["sha256"]] = store.blob_path(item["sha256"]).read_bytes()
    manifest = {"analysis_id": report_id, "report_sha256": report["report_sha256"],
                "anchor_hash": report["integrity"]["anchor_hash"],
                "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in contents.items()},
                "limitation": "Retain this manifest hash externally. A package is not digitally signed; replacing the whole package cannot be detected without an external anchor."}
    manifest_raw = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False).encode()
    manifest_hash = hashlib.sha256(manifest_raw).hexdigest()
    contents["manifest.json"] = manifest_raw
    contents["README.txt"] = ("PRATYAKSH EVIDENCE PACKAGE\nExtract the ZIP, then run: python3 verify.py\n"
        "For stronger checking, supply an independently retained manifest hash:\npython3 verify.py --expected-manifest " + manifest_hash +
        "\nThe tool uses only the Python standard library. Check the verifier source before running it.\n"
        "Original filenames and SHA-256 values are listed in report.json and report.pdf.\n"
        "Metadata and reviewer notes are assertions, not proof of origin. No legal verdict or digital signature.\n").encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in contents.items():
            bundle.writestr(name, raw)
    raw = stream.getvalue()
    store.log_action(report, "evidence_package_generated", {"analysis_id": report_id,
                     "package_sha256": hashlib.sha256(raw).hexdigest(), "manifest_sha256": manifest_hash})
    return Response(raw, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{report_id}-evidence.zip"',
        "X-Manifest-SHA256": manifest_hash})
