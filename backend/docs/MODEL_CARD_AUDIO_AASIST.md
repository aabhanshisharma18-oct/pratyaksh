# Model card: D1 AASIST audio anti-spoofing candidate

## Status

Days 2-3 research candidate. The official pretrained checkpoint runs locally,
and a deterministic class-balanced ASVspoof 2019 LA pilot has been measured.
The API still returns an `inconclusive` probe result because product-facing
threshold integration and wording have not been approved.

## Method

- Model: `clovaai/AASIST`
- Official source revision: `a04c9863f63d44471dde8a6abcb3b082b07cd1d1`
- Checkpoint SHA-256:
  `51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0`
- Source licence: MIT
- Positive evaluation class: spoof/synthetic speech
- Preprocessing: FFmpeg mono 16 kHz float audio; first 64,600 samples; shorter
  accepted recordings repeated to 64,600 samples
- Preprocessing version: `ffmpeg-mono-16khz-first64600-repeat-v1`

The raw spoof-class softmax output is not a calibrated probability that a voice
is cloned.

## Measured pilot

The frozen development threshold `0.5417414307594299` produced 97.6089%
accuracy and 97.5932% balanced accuracy over 3,973 successfully processed
held-out clips. Spoof recall was 95.2864%, bona-fide specificity was 99.9000%
and empirical EER was 0.7048%. Twenty-seven of 4,000 selected test clips were
rejected for being shorter than one second.

See `ASVSPOOF2019_LA_PILOT_RESULTS.md` for the sampling method, confidence
intervals, confusion matrix, reproduction command and limitations.

## Intended use

Research evaluation and triage for logical-access speech spoofing, including the
attack families represented by the labelled evaluation dataset. It is not a
speaker-identity system, provenance method, universal clone detector or proof of
authenticity.

## Known limitations

- AASIST was trained on ASVspoof 2019 LA; modern voice-cloning systems and
  real-world channels can differ substantially.
- Only about 4.04 seconds from the beginning of each accepted recording are
  scored by the current adapter.
- Silence and recordings shorter than one second are rejected rather than
  classified.
- Compression, background noise, music, overlapping speakers and language or
  microphone shifts can change the score.
- The measured result is a balanced pilot on ASVspoof 2019 LA, not a complete
  benchmark or a guarantee for modern real-world voice clones.
- The publisher's reported checkpoint result is not treated as Pratyaksh's
  measured result; this project must reproduce evaluation with its own pinned
  adapter and report the resulting metrics.

## Selection requirement

Use a licensed, group-separated development and held-out test collection. Freeze
the threshold on development only, then report held-out accuracy, spoof recall,
bonafide specificity, false-positive and false-negative rates, ROC-AUC, average
precision, EER, coverage and attack-family breakdowns. Dataset media, protocols
and prediction files remain local and must not be committed.

## Primary references

- Official AASIST repository: https://github.com/clovaai/aasist
- Official ASVspoof database access: https://www.asvspoof.org/database
- ASVspoof 2019 challenge: https://www.asvspoof.org/index2019.html
