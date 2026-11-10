"""Run the pinned D1 image candidate over one manifest split.

Evaluation media stays local. The output contains sample IDs, hashes, execution
status and raw model signals, but never copies or embeds the source images.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path

from PIL import Image, ImageOps

from detector import ImageDetector, MODEL_ID, REVISION
from evaluation.evaluate_predictions import load_json, validate_manifest

MAX_BYTES = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


def run_samples(
    samples: list[dict], base_dir: Path, split: str, detector: ImageDetector
) -> list[dict]:
    records = []
    for sample in samples:
        if sample["split"] != split:
            continue
        started = time.perf_counter()
        record = {
            "sample_id": sample["sample_id"],
            "execution_status": "failed",
            "model_id": MODEL_ID,
            "model_revision": REVISION,
            "preprocessing_version": "ufd-center-crop-224-clip-normalize-v1",
        }
        try:
            path = (base_dir / sample["path"]).resolve()
            raw = path.read_bytes()
            if not raw or len(raw) > MAX_BYTES:
                raise ValueError("image is empty or exceeds 15 MiB")
            digest = hashlib.sha256(raw).hexdigest()
            if digest != sample["sha256"]:
                raise ValueError("manifest SHA-256 does not match the image")
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("unsupported image format")
                if getattr(source, "n_frames", 1) != 1:
                    raise ValueError("animated image is unsupported")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
            if min(image.size) < 32:
                raise ValueError("image must be at least 32 pixels in each dimension")
            prediction = detector.predict(image)
            score = prediction.get("deepfake_score")
            if (
                not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not 0 <= score <= 1
            ):
                raise ValueError("detector returned an invalid score")
            record.update(
                {
                    "execution_status": "completed",
                    "deepfake_score": float(score),
                    "input_sha256": digest,
                    "width": image.width,
                    "height": image.height,
                }
            )
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["runtime_ms"] = round((time.perf_counter() - started) * 1000)
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "test"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    samples = validate_manifest(load_json(args.manifest))
    records = run_samples(samples, args.manifest.parent, args.split, ImageDetector())
    if not records:
        raise ValueError(f"manifest contains no {args.split} samples")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"split": args.split, "prediction_count": len(records)}, indent=2))


if __name__ == "__main__":
    main()
