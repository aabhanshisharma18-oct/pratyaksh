"""Validate a held-out manifest and score saved D1 media predictions.

This intentionally evaluates saved outputs rather than running inference. It keeps
model execution, threshold selection, and final test-set measurement as separate,
auditable steps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

LABELS = {"genuine", "synthetic"}
SPLITS = {"development", "test"}
SCHEMA_VERSIONS = {"1.0", "1.1"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict) -> list[dict]:
    schema_version = manifest.get("schema_version")
    if schema_version not in SCHEMA_VERSIONS:
        raise ValueError("manifest schema_version must be 1.0 or 1.1")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("manifest must contain a non-empty samples list")

    ids: set[str] = set()
    groups: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        required = {"sample_id", "path", "sha256", "label", "split", "group_id", "source", "terms"}
        if schema_version == "1.1":
            required |= {
                "media_type",
                "manipulation_type",
                "ground_truth",
                "transformation",
            }
        missing = required - sample.keys()
        if missing:
            raise ValueError(f"sample is missing fields: {sorted(missing)}")
        sample_id = sample["sample_id"]
        if sample_id in ids:
            raise ValueError(f"duplicate sample_id: {sample_id}")
        ids.add(sample_id)
        if sample["label"] not in LABELS:
            raise ValueError(f"unsupported label for {sample_id}: {sample['label']}")
        if sample["split"] not in SPLITS:
            raise ValueError(f"unsupported split for {sample_id}: {sample['split']}")
        if not isinstance(sample["source"], str) or not sample["source"].strip():
            raise ValueError(f"source must be documented for {sample_id}")
        if not isinstance(sample["terms"], str) or not sample["terms"].strip():
            raise ValueError(f"terms must be documented for {sample_id}")
        if schema_version == "1.1":
            if sample["media_type"] not in {"image", "audio"}:
                raise ValueError(f"unsupported media_type for {sample_id}")
            manipulation = sample["manipulation_type"]
            if not isinstance(manipulation, str) or not manipulation.strip():
                raise ValueError(f"manipulation_type must be documented for {sample_id}")
            if sample["label"] == "genuine" and manipulation != "none":
                raise ValueError(f"genuine sample must use manipulation_type none: {sample_id}")
            if sample["label"] == "synthetic" and manipulation == "none":
                raise ValueError(f"synthetic sample must identify a manipulation type: {sample_id}")
            ground_truth = sample["ground_truth"]
            if not isinstance(ground_truth, dict) or not ground_truth.get("basis"):
                raise ValueError(f"ground_truth basis must be documented for {sample_id}")
        if len(sample["sha256"]) != 64:
            raise ValueError(f"sha256 must contain 64 hexadecimal characters for {sample_id}")
        try:
            int(sample["sha256"], 16)
        except ValueError as exc:
            raise ValueError(f"invalid sha256 for {sample_id}") from exc
        groups[sample["group_id"]].add(sample["split"])

    leaked = sorted(group for group, splits in groups.items() if len(splits) > 1)
    if leaked:
        raise ValueError(f"group leakage across development and test splits: {leaked}")
    return samples


def verify_files(samples: list[dict], base_dir: Path) -> None:
    for sample in samples:
        path = (base_dir / sample["path"]).resolve()
        if not path.is_file():
            raise ValueError(f"sample file is missing: {sample['sample_id']}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sample["sha256"]:
            raise ValueError(f"sample hash mismatch: {sample['sample_id']}")


def _divide(a: int | float, b: int | float):
    return round(a / b, 6) if b else None


def _wilson_interval(successes: int, total: int, z: float = 1.959964):
    """Return a two-sided 95% Wilson score interval for a binomial rate."""
    if not total:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return [round(max(0.0, centre - margin), 6), round(min(1.0, centre + margin), 6)]


def _binary_metrics(counts: Counter) -> dict:
    precision = _divide(counts["tp"], counts["tp"] + counts["fp"])
    recall = _divide(counts["tp"], counts["tp"] + counts["fn"])
    specificity = _divide(counts["tn"], counts["tn"] + counts["fp"])
    f1 = (
        None
        if precision is None or recall is None or precision + recall == 0
        else round(2 * precision * recall / (precision + recall), 6)
    )
    return {
        "accuracy": _divide(counts["tp"] + counts["tn"], sum(counts.values())),
        "precision_synthetic": precision,
        "recall_synthetic": recall,
        "false_negative_rate": _divide(counts["fn"], counts["tp"] + counts["fn"]),
        "specificity_genuine": specificity,
        "false_positive_rate": _divide(counts["fp"], counts["tn"] + counts["fp"]),
        "f1_synthetic": f1,
        "balanced_accuracy": (
            None
            if recall is None or specificity is None
            else round((recall + specificity) / 2, 6)
        ),
    }


def _ranking_metrics(scored: list[tuple[float, str]]) -> dict:
    """Return threshold-independent ROC-AUC, AP and an empirical EER point.

    ROC-AUC uses average ranks for tied scores. Average precision is the
    step-wise area under the precision-recall curve used by common ML tools.
    """
    positives = sum(label == "synthetic" for _, label in scored)
    negatives = sum(label == "genuine" for _, label in scored)
    if not positives or not negatives:
        return {
            "roc_auc": None,
            "average_precision": None,
            "equal_error_rate": None,
            "eer_threshold": None,
        }

    ordered = sorted(scored, key=lambda item: item[0])
    positive_rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        positive_rank_sum += average_rank * sum(
            label == "synthetic" for _, label in ordered[index:end]
        )
        index = end
    roc_auc = (
        positive_rank_sum - positives * (positives + 1) / 2
    ) / (positives * negatives)

    descending = sorted(scored, key=lambda item: item[0], reverse=True)
    true_positives = 0
    examined = 0
    precision_sum = 0.0
    index = 0
    while index < len(descending):
        end = index + 1
        while end < len(descending) and descending[end][0] == descending[index][0]:
            end += 1
        group_positives = sum(
            label == "synthetic" for _, label in descending[index:end]
        )
        true_positives += group_positives
        examined += end - index
        precision_sum += group_positives * (true_positives / examined)
        index = end
    eer_candidates = []
    positives_below = 0
    negatives_below = 0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        threshold = ordered[index][0]
        false_negative_rate = positives_below / positives
        false_positive_rate = (negatives - negatives_below) / negatives
        eer_candidates.append(
            (
                abs(false_negative_rate - false_positive_rate),
                (false_negative_rate + false_positive_rate) / 2,
                threshold,
            )
        )
        positives_below += sum(
            label == "synthetic" for _, label in ordered[index:end]
        )
        negatives_below += sum(
            label == "genuine" for _, label in ordered[index:end]
        )
        index = end
    eer_candidates.append(
        (
            1.0,
            0.5,
            math.nextafter(ordered[-1][0], math.inf),
        )
    )
    _, equal_error_rate, eer_threshold = min(eer_candidates)

    return {
        "roc_auc": round(roc_auc, 6),
        "average_precision": round(precision_sum / positives, 6),
        "equal_error_rate": round(equal_error_rate, 6),
        "eer_threshold": eer_threshold,
    }


def _subgroup_results(assessed: list[dict], threshold: float) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in assessed:
        groups[item["manipulation_type"]].append(item)
    results = {}
    for name, items in sorted(groups.items()):
        labels = Counter(item["label"] for item in items)
        detected = sum(
            item["label"] == "synthetic" and item["score"] >= threshold
            for item in items
        )
        rejected = sum(
            item["label"] == "genuine" and item["score"] < threshold
            for item in items
        )
        results[name] = {
            "sample_count": len(items),
            "class_counts": dict(sorted(labels.items())),
            "synthetic_recall": _divide(detected, labels["synthetic"]),
            "genuine_specificity": _divide(rejected, labels["genuine"]),
        }
    return results


def _source_group_results(assessed: list[dict], threshold: float) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in assessed:
        groups[item["group_id"]].append(item)
    results = {}
    for name, items in sorted(groups.items()):
        counts = Counter(tp=0, tn=0, fp=0, fn=0)
        for item in items:
            predicted = "synthetic" if item["score"] >= threshold else "genuine"
            counts[
                {
                    ("synthetic", "synthetic"): "tp",
                    ("genuine", "genuine"): "tn",
                    ("synthetic", "genuine"): "fp",
                    ("genuine", "synthetic"): "fn",
                }[(predicted, item["label"])]
            ] += 1
        results[name] = {
            "sample_count": len(items),
            "confusion_matrix": dict(counts),
            "metrics": _binary_metrics(counts),
        }
    return results


def score_predictions(samples: list[dict], predictions: list[dict], threshold: float, split: str) -> dict:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    truth = {s["sample_id"]: s for s in samples if s["split"] == split}
    by_id: dict[str, dict] = {}
    for prediction in predictions:
        sample_id = prediction.get("sample_id")
        if sample_id in by_id:
            raise ValueError(f"duplicate prediction: {sample_id}")
        by_id[sample_id] = prediction

    counts = Counter(tp=0, tn=0, fp=0, fn=0)
    unavailable: list[dict] = []
    assessed: list[dict] = []
    for sample_id, sample in truth.items():
        prediction = by_id.get(sample_id)
        if not prediction or prediction.get("execution_status") != "completed":
            unavailable.append({
                "sample_id": sample_id,
                "status": prediction.get("execution_status", "missing") if prediction else "missing",
                "error": prediction.get("error") if prediction else "No prediction record",
            })
            continue
        score = prediction.get("deepfake_score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
            raise ValueError(f"invalid deepfake_score for {sample_id}")
        predicted = "synthetic" if score >= threshold else "genuine"
        actual = sample["label"]
        counts[{("synthetic", "synthetic"): "tp", ("genuine", "genuine"): "tn",
                ("synthetic", "genuine"): "fp", ("genuine", "synthetic"): "fn"}[(predicted, actual)]] += 1
        assessed.append(
            {
                "sample_id": sample_id,
                "score": float(score),
                "label": actual,
                "manipulation_type": sample.get(
                    "manipulation_type", "none" if actual == "genuine" else "unspecified"
                ),
                "group_id": sample["group_id"],
            }
        )

    examined = sum(counts.values())
    total = len(truth)
    positive_total = counts["tp"] + counts["fn"]
    negative_total = counts["tn"] + counts["fp"]

    class_counts = Counter(s["label"] for s in truth.values())
    ranking = _ranking_metrics(
        [(item["score"], item["label"]) for item in assessed]
    )
    return {
        "schema_version": "1.1",
        "split": split,
        "threshold": threshold,
        "sample_count": total,
        "examined_count": examined,
        "coverage": _divide(examined, total),
        "class_counts": dict(sorted(class_counts.items())),
        "confusion_matrix": dict(counts),
        "metrics": {**_binary_metrics(counts), **ranking},
        "confidence_intervals_95": {
            "accuracy": _wilson_interval(counts["tp"] + counts["tn"], examined),
            "recall_synthetic": _wilson_interval(counts["tp"], positive_total),
            "specificity_genuine": _wilson_interval(counts["tn"], negative_total),
            "method": "Wilson score interval",
        },
        "by_manipulation_type": _subgroup_results(assessed, threshold),
        "by_source_group": _source_group_results(assessed, threshold),
        "unavailable": unavailable,
        "notes": [
            "Metrics exclude unavailable or failed samples; coverage reports their effect separately.",
            "Select the threshold on development data before measuring the held-out test split.",
        ],
    }


def select_threshold(
    samples: list[dict], predictions: list[dict], objective: str = "balanced_accuracy"
) -> dict:
    """Select a threshold using development data only.

    Ties prefer higher synthetic recall, then the higher threshold. The held-out
    test split is deliberately unavailable to this function.
    """
    allowed = {"balanced_accuracy", "f1_synthetic"}
    if objective not in allowed:
        raise ValueError(f"unsupported threshold objective: {objective}")
    development = {
        sample["sample_id"]: sample
        for sample in samples
        if sample["split"] == "development"
    }
    scored = []
    for prediction in predictions:
        sample = development.get(prediction.get("sample_id"))
        score = prediction.get("deepfake_score")
        if (
            sample
            and prediction.get("execution_status") == "completed"
            and isinstance(score, (int, float))
            and not isinstance(score, bool)
            and math.isfinite(float(score))
            and 0 <= float(score) <= 1
        ):
            scored.append((float(score), sample["label"]))
    if not scored:
        raise ValueError("no completed development predictions are available")
    scores = sorted({score for score, _ in scored})
    candidates = {0.0, 1.0}
    candidates.update(scores)
    candidates.update((left + right) / 2 for left, right in zip(scores, scores[1:]))

    ordered = sorted(scored, reverse=True)
    positives = sum(label == "synthetic" for _, label in ordered)
    negatives = len(ordered) - positives
    true_positives = 0
    false_positives = 0
    cursor = 0
    coverage = _divide(len(ordered), len(development))
    ranked = []
    for threshold in sorted(candidates, reverse=True):
        while cursor < len(ordered) and ordered[cursor][0] >= threshold:
            if ordered[cursor][1] == "synthetic":
                true_positives += 1
            else:
                false_positives += 1
            cursor += 1
        counts = Counter(
            tp=true_positives,
            fp=false_positives,
            fn=positives - true_positives,
            tn=negatives - false_positives,
        )
        metrics = _binary_metrics(counts)
        value = metrics[objective]
        if value is not None:
            ranked.append(
                {
                    "threshold": threshold,
                    "objective_value": value,
                    "recall_synthetic": metrics["recall_synthetic"],
                    "false_positive_rate": metrics["false_positive_rate"],
                    "coverage": coverage,
                }
            )
    if not ranked:
        raise ValueError("development data must contain both genuine and synthetic samples")
    ranked.sort(
        key=lambda row: (
            row["objective_value"],
            row["recall_synthetic"] if row["recall_synthetic"] is not None else -1,
            row["threshold"],
        ),
        reverse=True,
    )
    return {
        "schema_version": "1.0",
        "selected_on_split": "development",
        "objective": objective,
        "threshold": ranked[0]["threshold"],
        "selection_metrics": ranked[0],
        "candidate_count": len(ranked),
        "warning": "Freeze this threshold before evaluating the held-out test split.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--split", choices=sorted(SPLITS), default="test")
    parser.add_argument("--verify-files", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    samples = validate_manifest(manifest)
    if args.verify_files:
        verify_files(samples, args.manifest.parent)
    predictions = load_json(args.predictions)
    if not isinstance(predictions, list):
        raise ValueError("predictions must be a JSON list")
    result = score_predictions(samples, predictions, args.threshold, args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
