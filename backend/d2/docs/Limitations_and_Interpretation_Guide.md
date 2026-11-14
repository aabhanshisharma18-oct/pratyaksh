# D2 Limitations and Interpretation Guide

## Integrity

`Hash Match` means the stored bytes equal the SHA-256 recorded at intake. `Hash Mismatch` means they differ or are unavailable. Neither result establishes whether depicted content is truthful, original, or manipulated. Integrity status is stored and shown separately from every analysis.

## Metadata

ExifTool and ffprobe output describes file-provided declarations and container structure. A software tag indicates declared association only; it does not prove original creator or intent. Missing camera tags are common and are never evidence of tampering. Unknown-zone timestamps remain explicitly unknown.

## Copy-move localization

The primary method groups identical overlapping grayscale blocks by displacement. It is deterministic and explainable, but repeated textures can create false matches. Resizing, rotation, recompression, color changes, or blending can hide copied regions. A localized region is a review lead—not a universal authenticity verdict. IoU, pixel agreement, precision, recall, and F1 are meaningful only against a documented mask.

## Video continuity

The video method samples at a configured fixed rate with hard frame and duration bounds. It compares exact decoded frame bytes and 64-bit average hashes. Static scenes and encoder behavior can create duplicate observations; sampling can miss edits. Results are continuity observations, not comprehensive tampering authentication.

## Correct language

Say “possible duplicated region,” “duplicate sampled-frame observation,” or “the bytes match the intake hash.” Do not say “fake,” “AI-generated,” “deepfake detected,” “tampering proved,” or “authentic.” Unsupported, failed, and partial states produce no negative conclusion.
