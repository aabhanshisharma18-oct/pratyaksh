# CP-SAT provenance pair selection

CP-SAT schedules geometric comparisons. It does not detect deepfakes, establish a relationship or improve a model's accuracy by itself.

## Use

Install `backend/requirements-provenance.txt` and restart the backend. On the provenance page choose **Visual comparison budget → CP-SAT · up to 8/16/32/48 pairs**, then run the comparison. **Compare all eligible pairs** remains the default.

The current upload limit remains 12 files, 15 MiB each and 60 MiB per batch. This change does not enable 100-file uploads.

API callers may supply positive integer `pair_budget` in the multipart `/api/d1/provenance/analyze` request or in the JSON case-comparison request. Omit it for exhaustive comparison. Budgets larger than the eligible set simply compare that entire set without calling the solver. Exact duplicates do not consume the visual budget. The API rejects a budget for which CP-SAT cannot find a covering selection; it never silently claims complete coverage.

## What happens

1. Inspect each supported file and prepare its bounded visual features as before. SIFT feature extraction still occurs per image; this optimisation targets pair matching, not all preprocessing.
2. Run all-pair SHA-256 and metadata checks. Exact-copy links are retained regardless of the visual budget.
3. Build eligible image/image and video/video pairs. dHash similarity gives image pairs a cheap integer priority. Video pairs currently receive equal priority.
4. Use one Boolean variable per eligible pair. Select at most the requested pair count (exactly that count when enough candidates exist), ensuring each file with eligible candidates participates in at least one selected comparison. Maximise the documented priority/tie-break objective.
5. Run the existing SIFT/RANSAC or bounded video-keyframe comparison on selected pairs. A candidate becomes a graph edge only if the existing matcher supports it.
6. Save selected, omitted, exact and unsupported pairs separately. The page and provenance PDF list unexamined pairs. Missing graph edges do not prove that files are unrelated.

Coverage of participating files is not coverage of every relationship. dHash can rank a genuine crop poorly. Budget units are file pairs, not seconds or video-frame pairs. Audio/mixed-media pairs have no geometric visual comparator and are counted separately.

OR-Tools runs with one worker, a fixed seed and a two-second solver limit. `OPTIMAL` means optimal for our heuristic selection objective, not optimal forensic accuracy. A feasible result can be used and labelled `FEASIBLE`; unresolved/infeasible planning returns an actionable error. The all-pairs mode does not need the solver.

## Recorded local pilot

Source: [cp-sat-benchmark.json](../../docs/evaluation/cp-sat-benchmark.json). Twelve generated geometric controls: four related files plus eight independently constructed controls. One untimed exhaustive warm-up; three timed runs per mode, rotating mode order. Timings include file inspection, feature preparation and matching. All run times are retained in the JSON.

| Method | Expensive visual pairs | Links retained relative to exhaustive | Median runtime |
| --- | ---: | ---: | ---: |
| Exhaustive | 65 / 65 | 6 / 6 | 1,983.23 ms |
| Greedy budget 12 | 12 / 65 | 6 / 6 | 1,605.87 ms |
| CP-SAT budget 12 | 12 / 65 | 6 / 6 | 1,637.91 ms |

One of the 66 total pairs was an exact duplicate and required no geometric comparison. CP-SAT omitted 53 eligible visual comparisons, an **81.54% reduction** in pair-verification calls. Its median end-to-end time was **17.41% lower** than exhaustive in this pilot. It was slightly slower than greedy. Its first timed run took 2,212.05 ms; do not hide this startup/solver overhead or present the median as every request's latency.

A separate planner-only check selected 200 of 4,950 candidates for 100 artificial items, covered all 100 and returned `OPTIMAL` in about 268.55 ms. That check uses synthetic integer priorities: no images, decoding or geometric matching. It is not an end-to-end 100-file benchmark.

These measurements establish software execution on the stated controls, not general provenance recall, real-world scalability, deepfake accuracy, or superiority to competing products. Reference retention is relative to this matcher and is not an independent ground-truth estimate.

Reproduce from the backend directory with a fresh output path:

```bash
./.venv/bin/python -m evaluation.benchmark_pair_selection \
  --output evaluation/results/cp-sat-reproduction.json --repeats 3
```

Official solver documentation: https://developers.google.com/optimization/cp/cp_solver/
