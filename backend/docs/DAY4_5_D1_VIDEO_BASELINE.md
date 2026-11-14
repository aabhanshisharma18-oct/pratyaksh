# Days 4-5 - D1 video baseline

Owner: Aabhanshi  
Status: implemented candidate; video-specific evaluation pending

## Implemented behavior

- Added `POST /api/d1/analyze-video` as a standalone D1 inference endpoint.
- Enforces a 50 MiB upload limit, a 120-second duration limit and bounded pixel dimensions.
- Uses FFprobe to read the first video stream and its presentation timestamps.
- Selects at most 12 real source timestamps near the centres of two-second sampling bins.
- Uses FFmpeg to decode one RGB frame for each selected timestamp.
- Applies the pinned UniversalFakeDetect whole-image candidate independently to each decoded frame.
- Returns per-frame timestamps and raw scores, rejected samples, examined coverage, and separate mean and maximum summaries.
- Records the input hash, method revision, preprocessing identity, runtime and limitations.
- Discards the uploaded bytes and decoded frames after the request.

## Interpretation boundary

The frame scores are synthetic-image model signals. They are not probabilities
that the video is fake. The arithmetic mean and maximum are exposed for later
evaluation but neither is a validated video aggregation rule. The endpoint does
not examine motion consistency, lip synchronization, the audio track, or frames
between the selected timestamps. Every successful result remains `inconclusive`.

## Acceptance evidence

- [x] Invalid, empty, oversized and undecodable inputs fail explicitly.
- [x] Sampling uses recorded presentation timestamps rather than assuming a constant frame rate.
- [x] Sample count, rejected samples and coverage are returned.
- [x] The checked-in MP4 fixture passes real FFprobe and FFmpeg extraction in automated tests.
- [x] The image detector is invoked separately for every successfully decoded frame.
- [x] No threshold or final video verdict is enabled.
- [x] A hashed manifest runner records timestamped frame outputs and supports explicit mean or maximum aggregation.
- [x] Group-separated development/test manifests accept video without treating frames as independent samples.
- [ ] Accuracy is measured on a permitted, source-separated genuine/manipulated video dataset.
- [ ] A development-only aggregation rule and threshold are selected and frozen.
- [ ] The frozen configuration is measured once on a held-out video test split.

The unchecked evaluation work is required before this candidate can become a
supported video classifier.
