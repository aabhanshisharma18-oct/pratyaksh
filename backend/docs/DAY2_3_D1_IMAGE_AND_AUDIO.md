# Days 2-3 — D1 image path and audio probe

Owner: Aabhanshi  
Status: implemented as unevaluated candidates  
Contract: D1 version `1.0`

## Image candidate path

- Added official UniversalFakeDetect `CLIP:ViT-L/14` as the active candidate.
- Pinned the official source revision, linear-head checkpoint and OpenAI CLIP
  backbone by SHA-256.
- Matched the official evaluation preprocessing: RGB, 224-pixel centre crop,
  tensor conversion and CLIP normalization.
- Exposed the raw logit and sigmoid synthetic-image score without enabling a
  project threshold or final verdict.
- Retained input hash, runtime, method identity and limitations in the result.

The contract-V1 label `Deepfake` represents its synthetic-image positive class.
UniversalFakeDetect is a whole-image AI-generation detector, not a face-swap-only
detector.

## Audio execution probe

- Added AASIST pinned to its official source and pretrained checkpoint.
- Added FFmpeg decoding to mono 16 kHz float audio, a 30-second bound, minimum
  duration and silence/low-energy gates.
- Reproduced the official evaluation input: first 64,600 samples, repeating shorter
  accepted audio to the required length.
- Verified label direction from the official data utility: index `0` is spoof and
  index `1` is bonafide.
- Added `POST /api/d1/probe-audio`, always marked `execution_probe_only` and
  `inconclusive`.

AASIST was trained for ASVspoof logical-access anti-spoofing. It is not a universal
voice-clone detector and requires permitted held-out genuine and spoof evaluation.

## Acceptance evidence

- [x] Image candidate source and both checkpoints are pinned by hash.
- [x] Image preprocessing and score direction match the official evaluation path.
- [x] Image API has bounded decode and explicit unavailable/failure handling.
- [x] Audio source and checkpoint are pinned by hash.
- [x] Audio decode, duration, energy and model-input gates are implemented.
- [x] Raw results remain inconclusive with limitations and no threshold.
- [x] Automated tests cover valid, invalid, unavailable and traceability paths.
- [ ] Accuracy is measured on a permitted, group-separated project dataset.
- [ ] Candidate acceptance and operating thresholds are frozen.

The unchecked items are evaluation work, not hidden Day 2-3 implementation.

## Deferred

- Video frame sampling and aggregation.
- Robustness and held-out accuracy measurement.
- D2 evidence intake and derivative registration.
- D4 main-dashboard integration and investigator-facing review workflow.
