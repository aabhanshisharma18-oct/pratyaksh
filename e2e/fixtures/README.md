# D4 E2E fixture provenance

`valid.png`, `partial.png`, `failed.png`, and `inconclusive.png` are byte-identical copies of `PRATYAKSH-test-evidence/01-original-intake.png`. That image was generated locally for this repository's test-evidence pack; its SHA-256 is recorded in `PRATYAKSH-test-evidence/SHA256SUMS.txt`. The filenames select deterministic test-worker outcomes only when the guarded E2E environment is active.

`valid.wav` and `valid.mp4` are copies of `03-synthetic-voice.wav` and `04-motion-test.mp4` from the same locally generated pack. The WAV is synthetic audio and the MP4 is synthetic motion; no third-party or personal media is included. `corrupt.png`, `corrupt.wav`, and `corrupt.mp4` are short ASCII strings created for negative decode tests. `evaluation.json` is a synthetic contract-valid publication and makes no accuracy claim.
