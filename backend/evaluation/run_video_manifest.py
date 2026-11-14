"""Run the D1 sampled-frame candidate over one labelled video manifest split.

Evaluation videos stay local. Output records retain hashes, timestamped raw frame
signals, rejected samples and the selected aggregation, but never embed media.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from detector import ImageDetector, MODEL_ID, REVISION
from evaluation.evaluate_predictions import load_json, validate_manifest
from video_probe import VideoSampler


MAX_BYTES = 50 * 1024 * 1024
PREPROCESSING_VERSION = (
    "ffprobe-pts-nearest-v1+ufd-center-crop-224-clip-normalize-v1"
)


def run_samples(
    samples: list[dict],
    base_dir: Path,
    split: str,
    sampler,
    detector,
    aggregation: str = "mean",
) -> list[dict]:
    if aggregation not in {"mean", "maximum"}:
        raise ValueError("aggregation must be mean or maximum")
    records = []
    for sample in samples:
        if sample["split"] != split:
            continue
        started = time.perf_counter()
        sampled = None
        record = {
            "sample_id": sample["sample_id"],
            "execution_status": "failed",
            "model_id": f"Timestamp sampling + {MODEL_ID}",
            "model_revision": REVISION,
            "preprocessing_version": PREPROCESSING_VERSION,
            "aggregation": aggregation,
        }
        try:
            if sample.get("media_type") != "video":
                raise ValueError("video runner requires media_type video")
            path = (base_dir / sample["path"]).resolve()
            raw = path.read_bytes()
            if not raw or len(raw) > MAX_BYTES:
                raise ValueError("video is empty or exceeds 50 MiB")
            digest = hashlib.sha256(raw).hexdigest()
            if digest != sample["sha256"]:
                raise ValueError("manifest SHA-256 does not match the video")

            sampled = sampler.sample(raw, path.name)
            frame_records = []
            rejected = list(sampled["rejected"])
            for index, frame in enumerate(sampled["frames"], start=1):
                try:
                    prediction = detector.predict(frame["image"])
                    score = prediction.get("deepfake_score")
                    if (
                        not isinstance(score, (int, float))
                        or isinstance(score, bool)
                        or not math.isfinite(score)
                        or not 0 <= score <= 1
                    ):
                        raise ValueError("detector returned an invalid score")
                    frame_records.append(
                        {
                            "sample_id": f"FRAME-{index:03d}",
                            "timestamp_ms": frame["timestamp_ms"],
                            "deepfake_score": float(score),
                        }
                    )
                except Exception as exc:
                    rejected.append(
                        {
                            "timestamp_ms": frame["timestamp_ms"],
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
                    )
            if not frame_records:
                raise ValueError("no sampled frame produced a valid model output")
            scores = [frame["deepfake_score"] for frame in frame_records]
            aggregated = sum(scores) / len(scores) if aggregation == "mean" else max(scores)
            record.update(
                {
                    "execution_status": "completed",
                    "deepfake_score": aggregated,
                    "input_sha256": digest,
                    "video": sampled["metadata"],
                    "requested_samples": sampled["requested_count"],
                    "examined_samples": len(frame_records),
                    "rejected_samples": rejected,
                    "frame_predictions": frame_records,
                    "mean_frame_score": sum(scores) / len(scores),
                    "maximum_frame_score": max(scores),
                }
            )
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if sampled:
                for frame in sampled.get("frames", []):
                    frame["image"].close()
        record["runtime_ms"] = round((time.perf_counter() - started) * 1000)
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "test"), required=True)
    parser.add_argument("--aggregation", choices=("mean", "maximum"), default="mean")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    samples = validate_manifest(load_json(args.manifest))
    records = run_samples(
        samples,
        args.manifest.parent,
        args.split,
        VideoSampler(),
        ImageDetector(),
        args.aggregation,
    )
    if not records:
        raise ValueError(f"manifest contains no {args.split} samples")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidate": "sampled_frame_video",
                "split": args.split,
                "aggregation": args.aggregation,
                "prediction_count": len(records),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
