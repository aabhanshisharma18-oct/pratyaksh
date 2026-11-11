"""Select and record a D1 media threshold on development data only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.evaluate_predictions import (
    load_json,
    select_threshold,
    validate_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--objective",
        choices=("balanced_accuracy", "f1_synthetic"),
        default="balanced_accuracy",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    samples = validate_manifest(load_json(args.manifest))
    predictions = load_json(args.predictions)
    if not isinstance(predictions, list):
        raise ValueError("predictions must be a JSON list")
    result = select_threshold(samples, predictions, args.objective)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
