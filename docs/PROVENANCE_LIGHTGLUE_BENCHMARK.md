# LightGlue provenance pilot

The current OpenCV SIFT matcher found 17 of 20 known photo relationships and linked 10 of 30 different-source pairs. SIFT with LightGlue found 16 of 20 known relationships and linked 7 of 30 different-source pairs. All false links came from the identical interface framing in simulated screenshots. The two images in each of those controls share interface pixels but depict different source content.

| Pair type | Pairs | Current matcher links | LightGlue links |
| --- | ---: | ---: | ---: |
| Original and crop | 5 | 4 | 4 |
| Original and JPEG recompression | 5 | 5 | 5 |
| Original and simulated screenshot | 5 | 5 | 5 |
| Original and small compressed crop | 5 | 3 | 2 |
| Different originals | 10 | 0 | 0 |
| Original and another source's compressed crop | 10 | 0 | 0 |
| Different sources in identical screenshot framing | 10 | 10 | 7 |

Median matching time was 5.3 ms for the current matcher and 573.5 ms for LightGlue on the local arm64 CPU. This single run timed the matcher and geometric verification with cached features. It excluded image decoding, feature extraction, and model loading.

Both paths used the same OpenCV SIFT keypoints and the existing RANSAC, inlier count, inlier ratio and region coverage checks. The baseline used its existing L2 ratio test. LightGlue used the official SIFT weights, RootSIFT descriptors, default match settings, and CPU inference with four Torch threads. The five source images produced correlated pairs. Screenshot framing and image transformations were simulated in memory. Further testing with independently collected sources, real screenshots and separate photos of similar scenes is needed before estimating performance on investigation data.

The live route retains its existing matcher. The pilot supports testing a way to isolate screenshot content from shared interface framing before evaluating a production change.

## Reproduce

Use the backend virtual environment with OpenCV, Torch, Pillow and the HEIC decoder. Install the official LightGlue checkout's dependencies in an isolated benchmark environment. The tested checkout was [cvg/LightGlue at 5a650c4](https://github.com/cvg/LightGlue/tree/5a650c444718caffc2669dc0094cde908f42dd73). Use the [official SIFT checkpoint](https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv/sift_lightglue.pth). The benchmark verifies its SHA-256 before loading.

From the repository root:

```sh
backend/.venv/bin/python backend/evaluation/benchmark_provenance_lightglue.py \
  --lightglue /path/to/LightGlue \
  --weights /path/to/sift_lightglue.pth \
  --output /tmp/provenance-lightglue-results.json \
  'Pratyaksh-Phone-Provenance-Demo/A-phone-original.HEIC' \
  'testing/provenance/A-synthetic-base.png' \
  'testing/provenance/H-independent-ai-scene.png' \
  'testing/provenance/G-unrelated-app-screenshot.png' \
  'testing/authentication&tamp/intake-samples/01-original-intake.png'
```

The phone original is a private fixture. Substituting a different source image changes the tested pairs. The JSON output records the pair labels, decisions, inlier counts, timings, model configuration and revision.
