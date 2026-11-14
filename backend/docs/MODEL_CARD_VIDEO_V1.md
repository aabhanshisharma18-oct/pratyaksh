# Model card - sampled-frame video candidate v1

## Task and method

This candidate screens bounded videos by sampling timestamped frames and applying
`WisconsinAIVision/UniversalFakeDetect CLIP:ViT-L/14` to each frame. The source
revision and both checkpoint hashes are inherited from `MODEL_CARD_IMAGE_V2.md`.

## Input and preprocessing

- FFmpeg-decodable video, maximum 100 MiB and 120 seconds.
- First video stream only; minimum frame dimensions 32 x 32.
- At most 12 source presentation timestamps near the centres of two-second bins.
- Each decoded RGB frame uses the pinned image model's centre-crop and CLIP normalization.

## Output

The API returns raw per-frame synthetic-image signals and exposes their arithmetic
mean and maximum separately. It reports examined and rejected samples. No video
threshold or classification is configured, so the finding is always inconclusive.

## Evaluation status

Not evaluated on a video dataset. Image-level evaluation, including any image
threshold, does not establish video-level performance because frames from one
video are correlated and sampling can miss brief manipulations.

The evaluation runner can record either the mean or maximum frame signal at the
video level. These are candidates, not accepted rules. Aggregation and threshold
must be selected together on group-separated development videos, frozen, and then
measured once on a held-out video test split.

## Known limitations

- No temporal or motion-consistency analysis.
- No lip-sync or audio-track analysis.
- No face tracking or face-swap-specific video model.
- Unsampled frames are unexamined.
- FFmpeg decoding can change pixel representation before inference.
- Performance on recompressed, resized, variable-frame-rate and unseen-generator videos is unknown.

## Intended use

Research and prototype triage only. Do not use the raw signals as proof of
authenticity, manipulation, attribution, identity or guilt.
