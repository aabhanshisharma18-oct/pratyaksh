# Model card: D1 SBI face-forgery research candidate

## Status

Optional, unevaluated research candidate for a noncommercial college prototype.
It was added because the whole-image candidate produced a known face-swap false
negative. It must not be described as more accurate until the labelled evaluation
reports demonstrate an improvement.

## Method

- Classifier: SBI EfficientNet-B4, official FF-c23 checkpoint
- Checkpoint SHA-256: `2b05c2ba36ccb9e9f4f9e1aae9acd443ae2e6400ce725f56104fdb175d3c3267`
- Classifier licence: noncommercial research use only
- Face detector: OpenCV Zoo YuNet 2023mar
- YuNet SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
- YuNet licence: MIT
- Preprocessing: `yunet-0.6-pad12.5-resize380-rgb01-v1`
- Aggregation: maximum fake-class softmax signal across up to eight faces

Model files stay under the ignored local `models/` directory. The restricted SBI
source and checkpoint are not committed or redistributed by Pratyaksh.

## Intended use

Research comparison for face swaps and facial reenactment. It complements rather
than replaces the whole-image AI-generation candidate.

## Known limitations

- No Pratyaksh accuracy, threshold or calibration has been established.
- YuNet replaces RetinaFace from the publisher's evaluation, creating a measurable
  preprocessing domain difference.
- The model can fail on small, occluded, profile, heavily compressed or unseen
  manipulated faces.
- A no-face result is an abstention, not a genuine classification.
- The raw softmax signal is not a probability that the evidence is manipulated.

## Selection requirement

Compare this candidate with the whole-image model using the same group-separated
development and test manifests. Report false-negative rate for `face_swap` and
other manipulation types separately before considering any ensemble.
