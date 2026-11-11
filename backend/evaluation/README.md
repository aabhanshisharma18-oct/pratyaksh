# D1 media evaluation

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
empirical equal-error rate (EER), and recall/specificity grouped by manipulation
type. Never choose a threshold after looking at the held-out test labels. Overall
accuracy alone is insufficient: always inspect false negatives and each
manipulation subgroup.

## Evaluate the AASIST audio candidate

Audio uses the same manifest, split, threshold-selection and held-out evaluation
rules. Start from `manifest.audio.example.json`, set `media_type` to `audio`, use
`none` for genuine recordings and a
documented manipulation such as `text_to_speech` or `voice_conversion` for spoof
recordings. All recordings from the same speaker or source family must share a
`group_id` and stay in one split.

```bash
python -m evaluation.run_audio_manifest \
  --manifest evaluation/manifest.audio.local.json \
  --split development \
  --output evaluation/predictions-audio-development.json

python -m evaluation.select_threshold \
  --manifest evaluation/manifest.audio.local.json \
  --predictions evaluation/predictions-audio-development.json \
  --objective balanced_accuracy \
  --output evaluation/results/audio-threshold.json
```

After freezing the selected development threshold, run the audio runner on the
test split and pass its predictions plus that frozen threshold to
`evaluation.evaluate_predictions`. The runner verifies each file SHA-256 before
FFmpeg decoding. Failed, short and silent recordings remain visible in coverage.

The official AASIST checkpoint was trained and evaluated on ASVspoof 2019 LA.
Obtain `LA.zip` under the Open Data Commons Attribution License and place it at
`data/datasets/asvspoof2019/LA.zip`. On storage-constrained systems, evaluate
directly from the verified archive without extracting it:

```bash
python -m evaluation.run_asvspoof2019_la_archive \
  --split development \
  --manifest evaluation/manifest.asvspoof2019-la-development.local.json \
  --predictions evaluation/predictions-asvspoof2019-la-development.json \
  --journal evaluation/results/asvspoof2019-la-development.jsonl
```

The runner verifies the official archive SHA-256 before inference and appends a
durable journal after every sample. Rerun the same command to resume after an
interruption. Select and freeze a threshold using the completed development
outputs, then repeat with `--split test` and separate test filenames. The test
split is the official evaluation partition and contains attacks not present in
development. Never use it to tune the threshold.

To execute those stages automatically while preserving the same resumable
journals and development/test separation, run:

```bash
python -m evaluation.run_asvspoof2019_la_benchmark
```

Its `summary.json` contains the frozen threshold and only the final held-out
metrics; detailed attack-family results remain in `heldout-test-report.json`.

For a shorter, explicitly labelled pilot, use a deterministic class-balanced
subset. This does not replace the complete benchmark:

```bash
python -m evaluation.run_asvspoof2019_la_benchmark \
  --development-per-class 1000 \
  --test-per-class 2000
```

That pilot scores 2,000 development clips and 4,000 held-out test clips. Its
summary records the sampling method and warns that sampling uncertainty is
larger than for the complete split.

If sufficient disk space is available, the extracted alternative remains
`python -m evaluation.prepare_asvspoof2019_la`; it maps the official protocols,
hashes every FLAC in place and writes an ignored local manifest. Do not commit or
redistribute corpus audio. No project audio accuracy exists until the held-out
evaluation process has completed.

## Reproduce the DeepfakeTIMIT pilot

Download the official DeepfakeTIMIT archive and the 16 VidTIMIT subject ZIPs
listed in `prepare_deepfaketimit.py` into `data/datasets/`. Those archives,
derived frames, manifests, predictions and JSON reports remain local and are
ignored by Git.

```bash
python -m evaluation.prepare_deepfaketimit

python -m evaluation.run_image_manifest \
  --manifest evaluation/manifest.deepfaketimit.local.json \
  --split development --candidate whole_image \
  --output evaluation/predictions-deepfaketimit-whole-development.json

python -m evaluation.run_image_manifest \
  --manifest evaluation/manifest.deepfaketimit.local.json \
  --split test --candidate whole_image \
  --output evaluation/predictions-deepfaketimit-whole-test.json
```

Repeat the two prediction commands with `--candidate face_forgery` and distinct
output names to compare the optional SBI candidate. Select each threshold from
its development predictions, freeze it, and only then evaluate its test
predictions. The tracked pilot report records the exact commands, thresholds
and limitations. The evaluator now also reports 95% Wilson intervals and
per-pair results; the intervals describe sample-level uncertainty and do not
correct for repeated frames from the same source pair.
