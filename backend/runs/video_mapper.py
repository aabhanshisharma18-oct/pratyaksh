from __future__ import annotations

import uuid
from typing import Any


def map_video_response(payload: dict[str, Any], run_id: str, evidence_id: str) -> dict[str, Any]:
    """Map the existing D1 video response without inventing unsampled observations."""
    video = payload["video"]
    sampling = payload["sampling"]
    samples = payload.get("samples", [])
    rejected = sampling.get("rejected_samples", [])
    planned = int(sampling.get("requested_samples", len(samples) + len(rejected)))
    examined = len(samples)
    sample_records = [
        {"index": index, "timestamp_ms": int(sample["timestamp_ms"]), "status": "examined", "reason": None}
        for index, sample in enumerate(samples)
    ]
    sample_records.extend(
        {"index": len(sample_records) + index, "timestamp_ms": int(sample["timestamp_ms"]),
         "status": "unexamined", "reason": str(sample.get("reason") or "rejected")}
        for index, sample in enumerate(rejected)
    )
    known = len(sample_records)
    sample_records.extend(
        {"index": known + index, "timestamp_ms": None, "status": "unexamined", "reason": "sample_not_returned"}
        for index in range(max(0, planned - known))
    )
    coverage = {
        "planned": planned,
        "examined": examined,
        "rejected": len(rejected),
        "unexamined": max(0, planned - examined),
        "percent": (examined / planned * 100) if planned else 0.0,
        "duration_ms": int(video["duration_ms"]),
        "strategy": sampling.get("policy"),
        "sampling_interval_ms": 2000,
        "samples": sample_records,
    }
    finding_template = payload["finding"]
    findings = []
    for sample in samples:
        timestamp_ms = int(sample["timestamp_ms"])
        score = float(sample["deepfake_score"])
        findings.append({
            **finding_template,
            "schema_version": "1.1",
            "finding_id": "F-" + uuid.uuid4().hex,
            "run_id": run_id,
            "evidence_id": evidence_id,
            "observation": f"Sampled frame at {timestamp_ms} ms returned the model score recorded below.",
            "scope": "One timestamped sampled video frame",
            "score": {**finding_template["score"], "value": score},
            "location": {"kind": "point", "timestamp_ms": timestamp_ms},
            "support_refs": [sample["sample_id"]],
            "details": {"kind": "video_sample", "sample_id": sample["sample_id"],
                        "raw_logit": sample.get("raw_logit"), "module": "video_frame_analysis"},
            "fixture": False,
        })
    return {
        "findings": findings,
        "coverage": coverage,
        "video": video,
        "summary": {
            "examined_samples": examined,
            "planned_samples": planned,
            "coverage_percent": coverage["percent"],
            "partial_coverage": examined < planned,
            "message": (f"{examined} of {planned} bounded timeline samples were examined; "
                        "unexamined samples are not a pass.") if examined < planned else
                       f"All {planned} requested bounded timeline samples were examined; unsampled frames were not assessed.",
        },
    }
