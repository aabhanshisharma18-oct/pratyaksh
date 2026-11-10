# D1 image evaluation

This folder separates three stages that must not be conflated:

1. Select an operating threshold using only the `development` split.
2. Freeze the model revision, preprocessing version, and threshold.
3. Measure the frozen configuration once on the held-out `test` split.

Copy `manifest.example.json` to a local manifest and replace every placeholder.
Do not add restricted media to Git. Every sample needs a stable ID, SHA-256 hash,
ground-truth basis, manipulation type, source group, terms, transformation, and
split. A claim on a webpage is not sufficient ground truth unless its provenance
can be documented. Variants from the same source must share a `group_id`; the
evaluator rejects groups spanning development and test because that would leak
related media into the held-out measurement. `manifest.schema.json` describes
the version 1.1 fields for tooling that supports JSON Schema.

Save predictions as a JSON list:

```json
[
  {
    "sample_id": "IMG-TEST-001",
    "execution_status": "completed",
    "deepfake_score": 0.83
  },
  {
    "sample_id": "IMG-TEST-002",
    "execution_status": "failed",
    "error": "Decoder rejected the file"
  }
]
```

Generate that list directly from a local manifest split with the pinned image
candidate:

```bash
python -m evaluation.run_image_manifest \
  --manifest evaluation/manifest.local.json \
  --split development \
  --candidate whole_image \
  --output evaluation/predictions-development.json
```

For the optional face-specific research candidate, install and set it up first,
then use `--candidate face_forgery`. Keep its predictions in a separate file so
the two candidates can be compared on exactly the same labelled samples.

The runner verifies every image against its manifest SHA-256 before inference.
Failed samples receive an explicit error record and remain visible in coverage.
Run the `test` split only after the model configuration and threshold are frozen.

First select a threshold using development predictions only:

```bash
python -m evaluation.select_threshold \
  --manifest evaluation/manifest.local.json \
  --predictions evaluation/predictions-development.json \
  --objective balanced_accuracy \
  --output evaluation/results/image-v1-threshold.json
```

Record and freeze the selected threshold, model revision and preprocessing
version. Then produce held-out metrics with that already-frozen threshold:

```bash
python -m evaluation.evaluate_predictions \
  --manifest evaluation/manifest.local.json \
  --predictions evaluation/predictions-test.json \
  --threshold 0.72 \
  --split test \
  --verify-files \
  --output evaluation/results/image-v1-test.json
```

The output reports failures and coverage separately from classification metrics.
It includes false-negative and false-positive rates, ROC-AUC, average precision,
and recall/specificity grouped by manipulation type. Never choose a threshold
after looking at the held-out test labels. Overall accuracy alone is insufficient:
always inspect false negatives and each manipulation subgroup.
