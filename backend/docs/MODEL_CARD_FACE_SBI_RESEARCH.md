# Model card: D1 SBI face-forgery research candidate

## Status

Optional research candidate for a noncommercial college prototype. It was added
because the whole-image candidate produced a known face-swap false negative. A
small external DeepfakeTIMIT held-out pilot measured only 48.13% accuracy, so it
did not demonstrate an improvement and must not replace the whole-image
candidate.

## Method

- Classifier: SBI EfficientNet-B4, official FF-c23 checkpoint
- Checkpoint SHA-256: `2b05c2ba36ccb9e9f4f9e1aae9acd443ae2e6400ce725f56104fdb175d3c3267`
- Classifier licence: noncommercial research use only
- Face detector: OpenCV Zoo YuNet 2023mar
- YuNet SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
- YuNet licence: MIT
- Preprocessing: `yunet-0.6-letterbox32-pad12.5-resize380-rgb01-v2`
- Aggregation: maximum fake-class softmax signal across up to eight faces

Model files stay under the ignored local `models/` directory. The restricted SBI
source and checkpoint are not committed or redistributed by Pratyaksh.

## Intended use

Research comparison for face swaps and facial reenactment. It complements rather
than replaces the whole-image AI-generation candidate.

## Known limitations

- The external pilot is narrow and old; no representative Pratyaksh deployment
  accuracy or score calibration has been established. See
  `DEEPFAKETIMIT_PILOT_RESULTS.md`.
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

## Fine-tuning pilot

The table compares SBI candidates on the same 160 DeepfakeTIMIT face-swap test
images (80 genuine and 80 manipulated).

| Candidate | Accuracy | Swaps detected | Genuine images flagged |
| --- | ---: | ---: | ---: |
| Pretrained SBI | 48.13% | 48/80 | 51/80 |
| Fine-tuned final two blocks, 120 Celeb-DF v2 training clips | 88.13% | 63/80 | 2/80 |
| Fine-tuned final two blocks, 360 Celeb-DF v2 training clips | 83.13% | 58/80 | 5/80 |
| Fine-tuned final three blocks, 360 Celeb-DF v2 training clips | 81.25% | 57/80 | 7/80 |

The best run fine-tuned the final two blocks and classifier using 379 face crops
from Celeb-DF v2 training clips and DeepfakeTIMIT development images. It chose
six epochs and a cutoff of 0.036994744 from leave-one-pair-out development
predictions. The test split was reused to compare experiments. Measure
generalization on a fresh identity-disjoint test before enabling a verdict in
the live API.

The local best checkpoint is `sbi-last-two-blocks.pt` under
`evaluation/results/sbi-timit-two-blocks-20261111-232032/`. Its SHA-256 is
`903f28007457c9bb6e21379a4858e87bf9ea4ca7a2ef6781ab267cac867eb97c`.

From the backend directory, run `python -m evaluation.train_sbi_pilot --help`
for the initial Celeb-DF classification-head training command. The 88.13% run
used additional development data and unfroze backbone layers.

## Local serving connection

The API defaults to the locally available still-image pilot, with an explicit
original-model override described in the backend README. Its pinned checkpoint
is 08a39359e5b3a2700ff32ae27fbc908a8b7993a50caec11a4b9bd3a0f0d576c9.
This pilot used 4,514 eligible training crops and 662 development crops. The
recorded test result was 543/685 correct (79.27%), with 315 of 1,000 test images
unscored. Related identities remain unverified and the test split was reused
for comparisons.

The verified checkpoint supplies its development cutoff of 0.5533131957054138.
The API binds that research cutoff to the model version and checkpoint hash,
and the interface flags individual faces crossing it. The overall file stays
inconclusive because multi-face aggregation and probability calibration need
separate validation.

An integration check on 40 previously evaluated eligible test images reproduced
saved pilot scores within 0.000004. At the saved pilot cutoff, 36/40 were correct.
The original FF-c23 checkpoint scored 23/40 at an exploratory reference cutoff
of 0.5. This subset checks serving behavior and offers no independent accuracy
estimate. The demonstration image was excluded from selection and cutoff tuning.
