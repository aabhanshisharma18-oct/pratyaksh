"""Run the pinned AASIST candidate over one labelled audio manifest split.

Evaluation audio stays local. Output records contain sample IDs, hashes,
execution status and raw spoof signals, but never copy or embed source audio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from audio_probe import AASISTProbe, MODEL_ID, PREPROCESSING_VERSION, REVISION
from evaluation.evaluate_predictions import load_json, validate_manifest

MAX_BYTES = 25 * 1024 * 1024


def run_samples(
    samples: list[dict],
    base_dir: Path,
    split: str,
    probe,
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
            "preprocessing_version": PREPROCESSING_VERSION,
        }
        try:
            if sample.get("media_type") != "audio":
                raise ValueError("audio runner requires media_type audio")
            path = (base_dir / sample["path"]).resolve()
            raw = path.read_bytes()
            if not raw or len(raw) > MAX_BYTES:
                raise ValueError("audio is empty or exceeds 25 MiB")
            digest = hashlib.sha256(raw).hexdigest()
            if digest != sample["sha256"]:
                raise ValueError("manifest SHA-256 does not match the audio")
            output = probe.probe(raw)
            score = output.get("model", {}).get("spoof_score")
            if (
                not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not 0 <= score <= 1
            ):
                raise ValueError("audio detector returned an invalid score")
            decoded = output.get("decoded", {})
            record.update(
                {
                    "execution_status": "completed",
                    "deepfake_score": float(score),
                    "input_sha256": digest,
                    "decoded_duration_ms": decoded.get("decoded_duration_ms"),
                    "sample_rate_hz": decoded.get("sample_rate_hz"),
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
    records = run_samples(samples, args.manifest.parent, args.split, AASISTProbe())
    if not records:
        raise ValueError(f"manifest contains no {args.split} samples")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidate": "audio_aasist",
                "split": args.split,
                "prediction_count": len(records),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
