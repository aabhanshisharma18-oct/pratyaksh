# Model card: D1 UniversalFakeDetect candidate

## Status

Days 2-3 candidate. The exact official checkpoints execute locally. A small
external DeepfakeTIMIT held-out pilot measured 68.75% accuracy, with a 45.00%
false-positive rate, so the result is not strong enough to enable an automatic
verdict. Every API result remains `inconclusive` and no production operating
threshold is enabled.

## Method

- Method: UniversalFakeDetect `CLIP:ViT-L/14`
- Official source revision: `030495aea3300a8b54c0ec37ec7fe1dd7e63c619`
- Linear-head SHA-256: `477100745713bcc957beb2b40859536859b6483fd6301b3b9293151b194c7847`
- CLIP backbone SHA-256: `b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836`
- Source license: MIT; OpenAI CLIP terms also require deployment review
- Raw output: linear logit; displayed score: sigmoid of that logit
- Preprocessing: `ufd-center-crop-224-clip-normalize-v1`

The publisher's reported results are not Pratyaksh's measured performance.

## Intended use

Research evaluation and investigator triage for possible AI-generated whole
images. It is not a face-swap specialist, tampering detector, provenance method or
authenticity certificate.

## Known limitations

- The external pilot is narrow and old; no representative Pratyaksh deployment
  accuracy or score calibration exists. See `DEEPFAKETIMIT_PILOT_RESULTS.md`.
- No manipulated-region localization or explanation heatmap is produced.
- Centre cropping can omit relevant border content.
- Compression, screenshots, edits, novel generators and natural-image domains can
  shift scores and cause false positives or false negatives.
- The complementary `Realism` value in contract V1 is `1 - synthetic_score`; it is
  a display aid, not a separately trained probability.

## Required evaluation before selection

- Group-separated development and held-out test collections.
- Permitted genuine and synthetic controls from multiple source families.
- Threshold chosen only on development data.
- Confusion matrix, precision, recall, specificity, F1, balanced accuracy,
  coverage, abstentions and failure counts on held-out data.
- Robustness checks for recompression, resizing, crops and screenshots.
