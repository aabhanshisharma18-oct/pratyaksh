# ASVspoof 2019 LA balanced pilot results

## Scope

This is a reproducible pilot measurement of the pinned AASIST adapter. It is
not a claim of universal real-world audio authenticity accuracy and it is not
the complete ASVspoof 2019 LA evaluation split.

- Dataset: official ASVspoof 2019 Logical Access archive
- Archive SHA-256:
  `208a7e4e3913f8c75ae1afd19bf32a5b29ae68435e9e30e23e5e98b6a155e4ec`
- Dataset terms: Open Data Commons Attribution License 1.0
- Model: `clovaai/AASIST`
- Source revision: `a04c9863f63d44471dde8a6abcb3b082b07cd1d1`
- Checkpoint SHA-256:
  `51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0`
- Preprocessing: FFmpeg mono 16 kHz; first 64,600 samples; shorter accepted
  recordings repeated to 64,600 samples
- Sampling seed: `pratyaksh-asvspoof-pilot-v1`

The deterministic class-balanced sample contained 1,000 bona-fide and 1,000
spoof development clips, followed by a separate held-out sample of 2,000
bona-fide and 2,000 spoof evaluation clips. The evaluation labels were not used
to select the operating threshold.

## Threshold selection

The threshold was selected on development data only by maximizing balanced
accuracy.

- Selected spoof threshold: `0.5417414307594299`
- Successfully processed development clips: 1,990 of 2,000
- Development balanced accuracy at selection: 99.6995%
- Development spoof recall at selection: 99.8990%
- Development false-positive rate at selection: 0.5000%

Ten development clips shorter than one second were rejected by the adapter and
excluded from threshold selection.

## Held-out results

The frozen threshold was then applied once to the held-out evaluation sample.

| Measure | Result |
| --- | ---: |
| Selected test clips | 4,000 |
| Successfully processed | 3,973 (99.325% coverage) |
| Accuracy on processed clips | 97.6089% |
| Balanced accuracy | 97.5932% |
| Spoof recall | 95.2864% |
| Bona-fide specificity | 99.9000% |
| False-negative rate | 4.7136% |
| False-positive rate | 0.1000% |
| ROC-AUC | 99.9723% |
| Average precision | 99.9717% |
| Empirical equal-error rate | 0.7048% |

Confusion matrix over the 3,973 processed clips:

- True spoof: 1,880
- True bona-fide: 1,998
- False spoof alarm: 2
- Missed spoof: 93

The sample-level 95% Wilson intervals were:

- Accuracy: 97.0858% to 98.0399%
- Spoof recall: 94.2600% to 96.1367%
- Bona-fide specificity: 99.6361% to 99.9726%

Twenty-seven held-out clips shorter than one second were rejected and are
reported as unavailable; the classification metrics exclude them. Coverage is
reported separately so those failures are not hidden.

## Interpretation and limitations

This result supports using AASIST as a research candidate for synthetic and
voice-converted speech resembling the ASVspoof 2019 LA conditions. It does not
prove that a recording is authentic, identify a speaker or establish
provenance. Performance can change for modern unseen generators, compression,
noise, music, overlapping speakers, languages and recording devices.

The complete official development and evaluation splits remain the stronger,
more expensive benchmark. Product-facing wording must identify this result as
a balanced pilot and must not present the spoof score as a calibrated
probability.

## Reproduction

With the licensed `LA.zip` stored locally at
`backend/data/datasets/asvspoof2019/LA.zip`:

```bash
cd backend
source .venv/bin/activate
python -m evaluation.run_asvspoof2019_la_benchmark \
  --development-per-class 1000 \
  --test-per-class 2000
```

Dataset audio, manifests, raw predictions and detailed local reports are
ignored by Git and must not be redistributed.
