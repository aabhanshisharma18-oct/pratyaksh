"""Derive a video-level aggregation from saved timestamped frame predictions."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path


def reaggregate(records: list[dict], aggregation: str) -> list[dict]:
    if aggregation not in {"mean", "maximum"}:
        raise ValueError("aggregation must be mean or maximum")
    result = deepcopy(records)
    field = "mean_frame_score" if aggregation == "mean" else "maximum_frame_score"
    for record in result:
        if record.get("execution_status") != "completed":
            continue
        score = record.get(field)
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ValueError(f"completed record is missing {field}: {record.get('sample_id')}")
        record["aggregation"] = aggregation
        record["deepfake_score"] = float(score)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--aggregation", choices=("mean", "maximum"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.predictions.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("predictions must be a JSON list")
    result = reaggregate(records, args.aggregation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "aggregation": args.aggregation,
                "prediction_count": len(result),
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
