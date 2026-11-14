# Screenshot interference benchmark

Pratyaksh uses geometric feature matching to link files that share visual content. An app header, sidebar, or toolbar can satisfy the same geometric check as a real image match. If two screenshots show different photos inside the same interface, the shared interface can produce a false photo link.

## Procedure

1. Generate 12 independent synthetic source families. Keep all variants of six sources in development and the other six in the test set. Each source has a crop, a JPEG recompression, and a Chrome screenshot of a controlled evidence viewer. It also has an independent render of the same synthetic scene layout.
2. Capture the browser pixels at 1200 by 900. Record the actual embedded photo's normalized rectangle from the rendered DOM. The browser and viewport are recorded in `browser.json`.
3. Build labeled pairs within each split. Positive pairs have known derivation. Negative pairs include different sources in the same browser frame, different source images with similar layouts, and independent renders of the same scene layout. The separate AI challenge uses a generated derivative with documented source history.
4. For the selected-area policy, tune the minimum inlier ratio on development pairs. Use the fewest false links, then the most true links, then the lowest ratio as tie breakers. Save the policy before scoring test pairs. The selected ratio was **0.55**. The whole-image comparison used the app's default **0.45**. Both used a 4-pixel RANSAC tolerance, at least 16 inliers, and the same spatial spread and hull coverage gates.
5. Score once on the held-out families. Use the recorded photo area for screenshot pairs. Separately check automatic proposals against those known boxes. The proposal needs analyst confirmation in the app.

## Results

| Held-out outcome | Whole image, ratio 0.45 | Recorded photo area, ratio 0.55 |
| --- | ---: | ---: |
| Known crops linked | 6/6 | 6/6 |
| JPEG recompressions linked | 6/6 | 6/6 |
| Known screenshots linked | 6/6 | 6/6 |
| False links from shared browser framing | 15/15 | 0/15 |
| False links across similar-layout sources | 3/15 | 0/15 |
| False links across independent renders of one layout | 0/6 | 0/6 |
| All true links | 18/18 | 18/18 |
| All false links | 18/36 | 0/36 |

Nominal 95% Wilson intervals are 82.4–100% for 18/18 true links, 34.5–65.5% for 18/36 false links, and 0–9.6% for 0/36 false links. Pairs share source families and screenshot chrome, so the intervals describe pair-level binomial uncertainty and can understate uncertainty across independent cases. The two columns differ in both area selection and ratio. Earlier manual-area testing with the same ratio removed 6/6 frame-induced false links while retaining 11/12 genuine links.

The stricter policy missed the separate AI-regenerated derivative that the default matcher linked. The live matcher retains its default 0.45 ratio while supporting analyst-selected areas. The original LightGlue pilot also recorded 10/30 false links for the baseline and 7/30 for LightGlue. Those counts came from a different pilot.

The rectangle proposal reached about 0.991 overlap with the recorded rectangle on each of 12 screenshots from this one interface. Real screens vary. The held-out link counts use the known rectangles. These assets are controlled browser captures and generated scenes. A second camera capture of the physical vase and real WhatsApp transfers require separate testing.

## Reproduce

With the backend requirements and Playwright Chromium installed, run from the repository root:

```sh
backend/.venv/bin/python backend/evaluation/benchmark_provenance_areas.py /tmp/pratyaksh-provenance-open-v1
```

Set `PRATYAKSH_CHROME_CHANNEL=chrome` to use installed Google Chrome. The output directory must be new. The dataset archive includes the source images, variants, screenshot masks as normalized rectangles, ground truth, threshold-selection record, per-pair results, browser details, proposal results, and asset SHA-256 values. The synthetic benchmark excludes the private phone photo.

## Judge questions

**What does a line prove?** A hash link shows identical bytes. A visual link means a set of points aligned under the recorded method. Source and editing order require additional evidence.

**What's the false-link rate?** Report the numerator, denominator and conditions. In the original pilot it was 10/30 with the baseline matcher. In the source-separated browser benchmark it was 18/36 with whole-image comparison and 0/36 using the recorded areas and frozen ratio. The nominal upper bound on that last count is 9.6%.

**How does this differ from pi-labs or Amped?** Pi-authentify advertises multimedia manipulation detection, localized analysis and reporting. Amped Authenticate offers image authentication and forensic examination. Demonstrate the specific Pratyaksh workflow: compare preserved files from one case, click a link to see its evidence, isolate the photo area when the surrounding interface repeats, and hand a reviewer an offline-verifiable package. [pi-authentify](https://www.pi-labs.ai/pi-authentify/) · [Amped Authenticate](https://ampedsoftware.com/authenticate)

**How do we verify a handover?** Retain the displayed manifest SHA-256 independently of the ZIP. On the receiving machine, extract the package and run the reviewed verifier:

```sh
python3 -I verify.py --expected-manifest "$(cat /path/to/independently-retained-fingerprint.txt)"
```

Flip one byte in an original in a disposable copy and run verification again. An isolated local receiver passed with the intact bundle and rejected the changed file. Repeating this on a second physical machine is still pending.

**How do we test forwarding?** Send each variant through WhatsApp and save the exact received file. Record the sender and receiver devices, app versions, send mode, and forwarding steps. Keep both files, compare their SHA-256 fingerprints and run provenance on each pair. The local JPEG degradation in this benchmark was performed by Pillow.
