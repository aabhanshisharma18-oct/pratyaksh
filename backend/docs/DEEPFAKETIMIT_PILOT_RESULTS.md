# DeepfakeTIMIT held-out pilot results

## Bottom line

Neither evaluated candidate is accurate enough to support an automatic
"real" or "deepfake" verdict. On this specific held-out pilot, the existing
whole-image candidate achieved **68.75% accuracy** and the optional SBI
face-forgery candidate achieved **48.13% accuracy**. The UI and API must
therefore continue to describe their output as an uncalibrated research signal.

These are measured results, not vendor claims. They apply only to the protocol
below and must not be presented as universal deepfake-detection accuracy.

## Protocol

- Dataset: official DeepfakeTIMIT higher-quality face-swap videos with their
  original VidTIMIT source sequences.
- Samples: one deterministic middle frame from each of 320 videos: 160 genuine
  and 160 synthetic.
- Development split: 8 identities in 4 source/target pairs; 80 genuine and 80
  synthetic samples.
- Held-out test split: 8 different identities in 4 different source/target
  pairs; 80 genuine and 80 synthetic samples.
- Leakage control: a source/target pair and all its derived samples are kept in
  exactly one split.
- Threshold selection: maximum balanced accuracy on the development split only.
- Test evaluation: threshold frozen before the test predictions were scored.
- Ground truth: dataset provenance, not a filename or internet-page claim.
- Coverage: 160/160 held-out samples for both candidates.

The preparation code verifies the official DeepfakeTIMIT MD5
`79b5dcee896ab825db43f1dfbdc8fdb5`, verifies each VidTIMIT ZIP CRC, hashes each
derived frame, and writes an ignored local manifest. The official download is
named `.tar.gz` although the pinned bytes are an uncompressed POSIX TAR; the
reader auto-detects the container after checksum verification.

## Held-out results

| Metric | Whole-image UFD | Face-specific SBI |
|---|---:|---:|
| Frozen threshold | 0.0014079590 | 0.2018575519 |
| Accuracy | **68.75%** | **48.13%** |
| Accuracy 95% Wilson CI | 61.20%–75.42% | 40.52%–55.82% |
| Fake recall | 82.50% | 60.00% |
| False-negative rate | 17.50% | 40.00% |
| Genuine specificity | 55.00% | 36.25% |
| False-positive rate | 45.00% | 63.75% |
| ROC-AUC | 0.7581 | 0.4839 |
| Average precision | 0.8101 | 0.5213 |
| Confusion matrix (TP/TN/FP/FN) | 66 / 44 / 36 / 14 | 48 / 29 / 51 / 32 |

The whole-image model varied from 50.0% to 87.5% accuracy across the four test
pairs. SBI varied from 15.0% to 70.0%. This instability is another reason not to
convert either score into a confident authenticity verdict.

Development balanced accuracy was 61.88% for both candidates at their selected
thresholds. The test numbers were not used to move those thresholds.

## Exact candidates

- Whole image: `WisconsinAIVision/UniversalFakeDetect CLIP:ViT-L/14`, revision
  `030495aea3300a8b54c0ec37ec7fe1dd7e63c619`, preprocessing
  `ufd-center-crop-224-clip-normalize-v1`.
- Face forgery: `Shiohara-Yamasaki/SBI EfficientNet-B4 FF-c23`, official
  checkpoint dated 2022-09-10, with YuNet face detection and preprocessing
  `yunet-0.6-pad12.5-resize380-rgb01-v1`.

## Reproduction

The local artifacts are intentionally not committed. Starting from the official
archives, run:

```bash
cd backend
source .venv/bin/activate
python -m evaluation.prepare_deepfaketimit
```

For each candidate, run `evaluation.run_image_manifest` on `development` and
`test`, run `evaluation.select_threshold` on development predictions, and pass
that frozen threshold to `evaluation.evaluate_predictions` for the test split.
The full command pattern is documented in `evaluation/README.md`.

## Limitations

- DeepfakeTIMIT is an older, controlled face-swap dataset. It does not represent
  modern diffusion images, every generator, social-media processing, or all
  real-world capture conditions.
- This pilot covers 16 identities and only 4 independent source/target pairs in
  the held-out split.
- One middle frame per video was evaluated; this is an image-detector pilot, not
  a temporal video evaluation.
- The Wilson intervals treat frames as observations and do not adjust for
  clustering within source/target pairs. Per-pair metrics expose some of that
  dependence but do not eliminate it.
- No fine-tuning was performed. Training on the test identities or selecting a
  threshold after seeing test labels would invalidate the reported result.
- A score below threshold does not prove authenticity, and a score above it
  does not prove fabrication.

## Sources

- DeepfakeTIMIT dataset and paper: https://www.idiap.ch/en/dataset/deepfaketimit
- Immutable DeepfakeTIMIT record: https://zenodo.org/records/4068245
- VidTIMIT originals and licence: https://conradsanderson.id.au/vidtimit/
