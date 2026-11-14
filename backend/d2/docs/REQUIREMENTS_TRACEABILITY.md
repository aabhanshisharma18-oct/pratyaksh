# D2 Requirements Traceability Matrix

Status was verified against the local implementation on 12 November 2026. “Complete (tool-dependent)” means the code and failure semantics are complete but ExifTool/ffprobe must be installed on the target machine.

| Requirement | Implementing file / function / endpoint | Test | Status |
|---|---|---|---|
| Concurrency-safe `CASE-YYYY-NNN-EVD-XXXXX` IDs | `intake/service.py::reserve_id` | `test_concurrency_safe_sequential_ids` | Complete |
| Streamed upload, single-pass SHA-256 | `intake/service.py::intake` | `test_streaming_hash_atomic_controlled_path_and_read_only` | Complete |
| Controlled path; filename never used in path | `intake/service.py::intake` | streaming/path test; API traversal filename test | Complete |
| Temp, fsync, atomic rename, read-only original | `intake/service.py::intake` | streaming/path test | Complete |
| Size, UTC receipt, context, uploader identity | `db.py::Evidence`; `POST /api/d2/evidence` | API intake test | Complete |
| Canonical SHA-256 and independent verification | `integrity/service.py`; `POST .../verify` | hash mismatch and API tests | Complete |
| Exact separate integrity status vocabulary | `db.py::Evidence.integrity_status`; D2 Integrity panel | mismatch and operator-page tests | Complete |
| Reverify before derivative/export | `DerivativeService.create`; `ExportService.create` | derivative and export tests | Complete |
| Separate derivative tree, full transformation record, parent verification | `derivatives/service.py`; `POST /api/d2/derivatives/{id}/verify-parent` | derivative linkage test | Complete |
| Append-only ordered audit events | `audit/service.py`; SQLite triggers in `db.py` | append-only test | Complete |
| Audit hash chain and verification action | `AuditService.verify`; `POST /api/d2/audit/verify` | chain-break test | Complete |
| Read-only ExifTool metadata | `metadata/service.py::extract` | metadata snapshot test | Complete (tool-dependent) |
| Read-only ffprobe streams/container metadata | `metadata/service.py::extract` | explicit tool/fallback snapshot behavior | Complete (tool-dependent) |
| Raw and normalized metadata views | metadata snapshot schema; D2 Raw/Normalized tabs | operator-page/API metadata test | Complete |
| Timestamps/timezones, software, dimensions/codecs/duration/bitrates/streams | `MetadataService.extract` normalized payload | metadata test | Complete |
| Neutral missing-camera message and required caveats | `metadata/service.py` constants; D2 UI | metadata/operator-page tests | Complete |
| Persist complete metadata snapshot and tool versions | `db.py::MetadataSnapshot` | metadata and export tests | Complete |
| Classical image copy-move method | `analysis/copy_move.py::CopyMoveAnalyzer` | copy-move localization test | Complete |
| Localization PNG mask and overlay | `CopyMoveAnalyzer`; `DerivativeService` | copy-move artifacts test | Complete |
| Algorithm/version/parameters/scores/regions stored | `AnalysisRun`; `save_analysis` | copy-move endpoint contract test | Complete |
| Image ground-truth mask metrics | `analysis/metrics.py::mask_metrics` | copy-move metrics test | Complete |
| Mandatory copy-move limitation | `copy_move.py::LIMITATION`; UI/export | unit and endpoint tests | Complete |
| Bounded fixed-rate video sampling | `analysis/video_continuity.py` | video duplicate test | Complete |
| Exact/near-exact duplicate frames and timestamps | `VideoContinuityAnalyzer.analyze` | video duplicate test | Complete |
| Video ground-truth frame metrics | `analysis/metrics.py::frame_metrics` | video metrics test | Complete |
| Mandatory continuity limitation | `video_continuity.py::LIMITATION`; UI/export | video test | Complete |
| Separate Integrity, Metadata, Manipulation panels | `ui/templates/d2.html` | `test_operator_page_has_separate_panels` | Complete |
| Uniform support/decoding/analysis statuses | `analysis/base.py::AnalysisResult` | corrupt and endpoint-contract tests | Complete |
| Human-readable unsupported/corrupt behavior | analyzers and API error translation | corrupt input test | Complete |
| Results include locations, artifact links, interpretation, limitations | `AnalysisRun`; analysis endpoints | endpoint test | Complete |
| Export-time verification, metadata, outputs, audit, limitations, hashes | `export/service.py` | export completeness test | Complete |
| Known-good, modified/mask, video sidecar, false alarm, corrupt/unsupported samples | `samples/generate.py`; root `samples/d2/` | generator execution in verification | Complete |
| Seeded demo with positive, false-alarm/limitation controls and evaluation report | `samples/generate.py`; `demo.py` | generated report validation | Complete |
| Streaming, traversal, mismatch, derivative, audit, metadata, analysis, status, export tests | `tests/test_d2.py`, `tests/test_api.py` | full D2 pytest suite | Complete |
| Required package structure and uniform analysis interface | `backend/d2/`; `analysis/base.py` | import/pytest collection | Complete |
| Deterministic thresholds and parameters documented | analyzer constructors; limitations guide | result-contract tests | Complete |
| Limitations and interpretation guide | `docs/Limitations_and_Interpretation_Guide.md` | documentation review | Complete |
| No deepfake/AI/proof claims or black-box model | UI, README, guide, deterministic analyzers | operator-page and text review | Complete |
| One-command demo | root `Makefile::demo`; `d2/demo.py` | command/import verification | Complete |
| Comprehensive setup, run, demo, architecture README | `backend/d2/README.md` | documentation review | Complete |

## Optional extensions

ELA, audio-discontinuity analysis, and recompression visualization were intentionally not implemented. Section 3.3 marks them optional; omitting them avoids distracting from the tested primary and fallback paths.

## Honest environment boundaries

- ExifTool and ffprobe are external executables. Their absence is recorded in the metadata snapshot rather than silently treated as “no metadata.”
- Read-only file permissions are a defense-in-depth flag, not an operating-system access-control boundary against an administrator.
- The ZIP manifest hashes every payload member. `manifest.json` cannot hash itself without recursion, so it explicitly documents its standard self-exclusion.
- Demo identity is configurable and explicitly self-declared; this prototype does not claim authenticated agency identity.
