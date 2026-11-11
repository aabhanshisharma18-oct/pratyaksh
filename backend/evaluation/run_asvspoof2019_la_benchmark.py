"""Run the complete, held-out ASVspoof 2019 LA benchmark for pinned AASIST."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from evaluation.evaluate_predictions import (
    load_json,
    score_predictions,
    select_threshold,
    validate_manifest,
)
from evaluation.run_asvspoof2019_la_archive import (
    DEFAULT_ARCHIVE,
    atomic_json,
    run_archive,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "evaluation" / "results" / "asvspoof2019-la"


def run_benchmark(
    archive: Path,
    results_dir: Path,
    development_per_class: int | None = None,
    test_per_class: int | None = None,
) -> dict:
    results_dir.mkdir(parents=True, exist_ok=True)
    development_manifest = results_dir / "manifest-development.local.json"
    development_predictions = results_dir / "predictions-development.json"
    development_journal = results_dir / "development.jsonl"
    test_manifest = results_dir / "manifest-test.local.json"
    test_predictions = results_dir / "predictions-test.json"
    test_journal = results_dir / "test.jsonl"

    development_run = run_archive(
        archive,
        "development",
        development_manifest,
        development_predictions,
        development_journal,
        batch_size=1,
        verify_archive=True,
        samples_per_class=development_per_class,
    )
    development_samples = validate_manifest(load_json(development_manifest))
    threshold = select_threshold(
        development_samples,
        load_json(development_predictions),
        "balanced_accuracy",
    )
    threshold_path = results_dir / "threshold.json"
    atomic_json(threshold_path, threshold)

    test_run = run_archive(
        archive,
        "test",
        test_manifest,
        test_predictions,
        test_journal,
        batch_size=1,
        verify_archive=False,
        samples_per_class=test_per_class,
    )
    test_samples = validate_manifest(load_json(test_manifest))
    report = score_predictions(
        test_samples,
        load_json(test_predictions),
        threshold["threshold"],
        "test",
    )
    report_path = results_dir / "heldout-test-report.json"
    atomic_json(report_path, report)

    summary = {
        "schema_version": "1.0",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "ASVspoof 2019 Logical Access",
        "model": "clovaai/AASIST",
        "evaluation_scope": (
            "complete official development and evaluation splits"
            if development_per_class is None and test_per_class is None
            else "deterministic class-balanced pilot subset"
        ),
        "sampling": {
            "development_per_class": development_per_class,
            "test_per_class": test_per_class,
            "seed": "pratyaksh-asvspoof-pilot-v1",
        },
        "development_run": development_run,
        "threshold_selection": threshold,
        "test_run": test_run,
        "heldout_test": {
            "sample_count": report["sample_count"],
            "coverage": report["coverage"],
            "class_counts": report["class_counts"],
            "confusion_matrix": report["confusion_matrix"],
            "metrics": report["metrics"],
            "confidence_intervals_95": report["confidence_intervals_95"],
        },
        "report": str(report_path),
        "limitations": [
            "This measures ASVspoof 2019 LA performance, not universal real-world accuracy.",
            "The benchmark covers synthetic and voice-converted speech, not speaker identity or provenance.",
            "Modern generators, codecs, noise and recording channels can have different error rates.",
            "A pilot subset has wider statistical uncertainty than the complete official split."
            if development_per_class is not None or test_per_class is not None
            else "The full official split does not cover every modern real-world generator.",
        ],
    }
    summary_path = results_dir / "summary.json"
    atomic_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--development-per-class", type=int)
    parser.add_argument("--test-per-class", type=int)
    args = parser.parse_args()
    print(
        json.dumps(
            run_benchmark(
                args.archive,
                args.results_dir,
                args.development_per_class,
                args.test_per_class,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
