# Temporal video experiment

## What changed

The existing video baseline still scores isolated frames with UniversalFakeDetect. A separate optional branch now samples up to 32 distinct presentation timestamps at 8 Hz within the opening four seconds, detects one face per frame with the existing verified YuNet model, extracts frozen CLIP ViT-L/14 features, and feeds those features in time order to an LSTM with 64 hidden units and a linear output head.

This adapts the sequence-analysis concept from the supplied ResNeXt/LSTM screenshots. Pratyaksh uses its existing CLIP encoder; it does not implement or claim to reproduce that tutorial's ResNeXt network or reported dataset size.

No trained temporal checkpoint or accuracy result is included with this implementation. Before training, the interface shows **Training required**. The independent frame scan remains available. There is no fabricated score and no new real/fake verdict.

## Safety and scope of an examination

- Videos retain the current 100 MiB and 120-second API limits.
- The sequence examines the opening four seconds only, not the whole video.
- At least 16 face frames are required. No face, multiple faces, decoder omissions, missing timestamps and abrupt face-box jumps cause abstention.
- Consecutive boxes must overlap, but this is not biometric identity verification and cannot guarantee a shot or identity did not change.
- At most 32 face boxes and their presentation timestamps are returned for review.
- A score above the development cutoff recommends review. A lower score does not prove authenticity.
- The raw sequence score is not a percentage of AI content. No probability calibration or validated fusion with UFD is claimed.
- A sequence failure does not discard a successful frame scan. Failure is shown separately.
- UI timeline dots are actual baseline samples; the lines between dots do not imply continuous examination.
- Completed sequence findings retain the model hash, window, cutoff, limitations, face boxes and benchmark metadata in the case/run record for the dashboard and report workflow.

## Prepare the training manifest

Create a JSON list. Paths are relative to the manifest. Labels are integer 0 for genuine and 1 for manipulated. Every row needs a group ID. All variants of a source video, and related identities where possible, must stay in the same group and split. The tool rejects a group crossing splits and duplicate file bytes. It cannot independently discover every re-encoded duplicate or identity relation; manually review those assignments.

```json
[
  {"path":"videos/genuine-a.mp4", "label":0, "split":"train", "group_id":"source-family-a"},
  {"path":"videos/edited-a.mp4", "label":1, "split":"train", "group_id":"source-family-a"},
  {"path":"videos/genuine-b.mp4", "label":0, "split":"development", "group_id":"source-family-b"},
  {"path":"videos/edited-b.mp4", "label":1, "split":"development", "group_id":"source-family-b"},
  {"path":"videos/genuine-c.mp4", "label":0, "split":"test", "group_id":"source-family-c"},
  {"path":"videos/edited-c.mp4", "label":1, "split":"test", "group_id":"source-family-c"}
]
```

This illustrates the format only. Each split must actually contain at least two videos in each class. Use substantially more for useful evaluation. Do not use the application's synthetic motion demo to measure deepfake accuracy.

## Train and evaluate

Run from the backend directory with the existing detector environment and verified CLIP/YuNet assets installed:

```bash
cd /Users/Dell/Desktop/pratyaksh/backend
./.venv/bin/python -m evaluation.train_temporal_video \
  --manifest /absolute/path/to/temporal-manifest.json \
  --output evaluation/results/temporal-video-run-01 \
  --epochs 8 \
  --device mps
```

CLIP feature extraction runs on CPU using the same adapter as inference. `--device` selects where the small LSTM trains. The encoder is frozen. The trainer processes variable-length single-video sequences and balances the training loss by class.

The best epoch and temporal cutoff are selected only on development clips. A separate development cutoff is selected for the UFD mean-score baseline. Test clips are decoded and scored after model selection. Both systems are measured on the same successfully extracted test clips and opening window. This is not a comparison against the full-video scan's sparse sampling policy.

Outputs:

- `head.pt`: trained LSTM weights.
- `manifest.json`: checkpoint/backbone fingerprints, preprocessing version, selected epoch and cutoff, split/class counts, extraction coverage, unscored failures, baseline and temporal test metrics, and limitations.
- `test-predictions.json`: per-video content fingerprints, labels, scores and examined timestamps.

Metrics include confusion counts, accuracy, balanced accuracy, synthetic recall, false-positive rate, precision and a Wilson interval for sample accuracy. Coverage is reported separately. Accuracy excludes unscored clips; neither accuracy nor its interval is a confidence score for an uploaded video.

Use a fresh output directory for each experiment. The script refuses to overwrite an existing result. Repeated experiments against the same test set still constitute test reuse; reserve a new final holdout if tuning after reading test results. Dataset scale alone does not ensure improvement.

## Activate only after review

Inspect coverage, false positives and the comparison first. If suitable for the intended research demo, copy `head.pt` and its matching `manifest.json` into `backend/models/temporal-video/`, then restart the backend. Serving checks the weights hash, encoder hash, preprocessing version and cutoff. Model files remain local and ignored by Git. Never replace the production detector merely because a small pilot has a higher accuracy.

The video page then shows the temporal signal, a development-cutoff explanation, the examined time window and the held-out benchmark counts. The overall outcome remains inconclusive because this experimental branch is not a validated forensic verdict.
