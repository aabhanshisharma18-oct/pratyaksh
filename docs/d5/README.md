# D5 reporting — persistent revisions and workspace

Bhumi owns the reporting frontend, backend, revisions and exports.

The D1 FastAPI application now registers these endpoints:

| Action | Endpoint |
| --- | --- |
| Save registered case records | `POST /api/cases/{case_id}/reports` with `{"preparer":"Bhumi"}` |
| List permanent revisions | `GET /api/cases/{case_id}/reports` |
| Reopen a revision | `GET /api/reports/{report_id}` |
| Download canonical JSON | `GET /api/reports/{report_id}/export?format=json` |
| Download JSON and hash manifest | `GET /api/reports/{report_id}/export?format=zip` |

The report table uses the case SQLite database (`PRATYAKSH_DB_PATH`). Each save creates a new ID and a monotonically increasing case revision. Existing snapshots have no update/delete API. Concurrent saves serialize revision allocation. Retrieval verifies stored bytes against SHA-256.

Report inputs come from registered case/evidence/finding/reviewer-note records, never a client-supplied verdict. Execution status, result, score semantics, method versions, limitations and artifact references remain in the saved finding records. Every evidence/channel combination explicitly records whether findings exist. A recorded finding may still describe a failure or inconclusive outcome; inspect its execution status and result.

Exports exclude original media and referenced artifact bytes. The manifest hashes the exact `report.json` bytes. These hashes provide consistency checking, not signatures, trusted timestamps or protection from a database administrator. Preparer names are self-declared. Source reads occur sequentially, so a save is not a transaction-wide snapshot of concurrent case changes.

Verify from the repository root:

```sh
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p test_reports.py -v
```

## Reports workspace

Set `VITE_API_BASE_URL=http://127.0.0.1:8000` and start the existing D1 service and Vite frontend. Open a case and select Reports. Enter a preparer name, save a revision, and reopen it from the revision history. JSON, ZIP and Print / Save as PDF all use the selected server snapshot. The readable preview includes evidence hashes and provenance of those hashes, source finding IDs and hashes, methods/versions, execution status, scores with interpretation/calibration, limitations, coverage, and saved reviewer notes. API errors remain visible and never fall back to browser-local reports. Without API configuration the existing browser-local report interface remains available.

Demo: save a revision, add a finding or reviewer note to the case, then reopen the original revision. It stays unchanged. Save again to capture the new case records in a second revision. Download its ZIP and compare the SHA-256 of `report.json` to `manifest.json`.

Frontend API contract tests: `npm test -- frontend/src/reports/api.test.ts`. Full frontend checks: `npm test` and `npm run build`.

Remaining D5 work: richer report templates, artifact-byte packaging policy, and genuine/manipulated/mixed/partial end-to-end demo scenarios. By default reports include all registered findings; the run selector can restrict a new revision to chosen finished runs, including failed and partial runs. It does not claim final D5 completion.

## Validation in this checkout

- 98 frontend tests pass, including nine D5 API contract tests, two section-presentation tests and two technical-detail rendering tests.
- Full TypeScript checking and Vite production build pass after dependency installation.
- Twenty-three backend tests pass on the installed Python 3.11 environment: twelve store tests, six FastAPI ASGI integration tests and five API scenario tests. The API tests exercise save, reopen, revision history, exact JSON/ZIP content and invalid requests without a network socket.
- The complete backend imports and reaches application startup. Live browser verification passed using the user-started services and a preserved repository test PNG: case creation, preservation, real header inspection, unavailable detector handling, report save/review, refresh/reopen and JSON/ZIP downloads. Print pagination remains unverified.

Run backend checks with:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -p 'test_reports*.py' -v
```

## Run selection (report schema d5.2)

`GET /api/cases/{case_id}/reports/run-options` lists case-scoped runs with registered findings. Saved run status is authoritative when available; otherwise status is explicitly derived from registered findings. Queued/running runs cannot be selected. Partial, failed, unsupported and cancelled terminal runs remain eligible when they have registered findings.

Pass `run_ids` with the preparer to save an explicit selection. Missing, duplicate, empty and unfinished selections are rejected. Omit `run_ids` to preserve the existing all-registered behavior. Reports save the selected IDs, selection mode and excluded-finding count. Only selected findings and their reviewer notes are copied; the full evidence inventory remains so missing coverage is visible. Coverage always describes the report scope, not unselected analyses. Old d5.1 revisions still open unchanged.

## Readable section selection (report schema d5.3)

The Reports workspace saves a `sections` array with each new revision. Evidence inventory and reviewer notes may be omitted from the readable preview/print. Methods, findings, examination coverage and limitations are required. Backend validation rejects unknown/duplicate section IDs and attempts to remove required content. Sections always render in document order with consecutive heading numbers.

This option is presentation only: JSON and ZIP retain the complete saved technical record, including evidence and notes. It is not redaction or access control. The UI and document state this distinction. Changing draft choices never changes a saved revision. Old d5.1/d5.2 revisions without section choices display all sections.

## Report review (reviewed revision schema d5.4)

`POST /api/reports/{report_id}/reviews` accepts `reviewer`, `status` (`reviewed` or `questioned`) and a required `note`. It creates a new case revision with a fresh ID, leaving its source unchanged. The server copies the exact verified saved snapshot rather than rereading current case records. Evidence, machine findings, original annotations, sections and run scope remain unchanged.

The new revision records its parent report ID/hash, original preparation time and an appended review-history entry with reviewer, time, status and note. A reviewer can review an older revision deliberately; its explicit parent link distinguishes that lineage from intervening case revisions. Reviewer identities are self-declared and review status is not an authenticity certificate or legal approval.

In Reports, reopen the intended revision and use **Review selected saved revision**. Saving review creates/selects the new revision; JSON, ZIP and print include its review record. Review history is always visible even if optional finding-note presentation is disabled. A fresh report generated from case data starts unreviewed. Old saved revisions remain readable.

## Detailed content and audit snapshot (schema d5.5)

New reports accept optional `questions` and `next_steps` (up to 2000 characters each). These are explicitly analyst-supplied statements attributed to the preparer, separate from automated findings. Receipt fields appear when the evidence inventory is selected. Findings render in evidence/category order with source IDs, locations and a technical-settings appendix.

The settings appendix displays only explicitly present fields in saved finding details: preprocessing/configuration versions, configuration, threshold, trust policy, model and weight hash. Missing settings are labelled **Not recorded in saved finding**. A recorded null and numerical zero remain distinct. Raw run files, model weights and external artifacts are not read or reconstructed here; richer run-level model/configuration records remain an integration gap when they are absent from published findings.

At creation the report captures up to the latest 500 case audit events via the published case repository. It saves counts by event type, event IDs/times, actors, summaries and evidence/run links. Counts refer only to included events; truncation is explicit. This is case-wide audit context even for a selected-run report. Arbitrary audit payloads are excluded. Actor identities are self-declared and this does not establish a full pre-upload custody history or independent tamper resistance.

Reopening and reviewing reports preserve their original audit and analyst context. Historical revisions lacking these fields show them as not captured; current audit data is never silently injected into an older snapshot. Browser print-layout remains pending; five illustrative API scenario checks pass.

## Published run context and artifact references (schema d5.6)

The integrated report service reads the existing RunRepository through its published `get_run` interface. It validates matching run, case and evidence IDs before copying configuration/version, execution status, requested checks, timing, coverage, errors and explicit per-check settings from event payloads. No model threshold or model configuration is inferred from the orchestrator's own configuration version. Run context is captured only for runs represented by the report's saved findings.

Each finding support reference is matched to published top-level or event artifact metadata. Records identify matching metadata, ambiguous matches or unresolved references. Only descriptive IDs, kind, declared SHA-256 and size are copied. Filesystem paths and download URLs are never followed. All artifact records explicitly state `bytes_verified=false` and `bytes_included=false`. Model weights and original files remain excluded.

Current integration gap: the shared run API publishes an empty top-level artifact list and does not provide a case-scoped artifact-byte retrieval contract. Event-level metadata can be captured when published; D2's separate derivative storage still needs an explicit case/evidence mapping before those bytes can be included or verified by D5. Metadata-only support must not be described as verified evidence images in a submission.

Revisions preserve captured context even if the run changes later. Review copies this context unchanged. Historical reports without run context show that it was not captured. Remaining checks include broader media/model browser demonstrations, five final sample scenario reports, print pagination, and any agreed artifact-byte integration.

## Five-scenario acceptance tests

The committed `test_reports_scenarios.py` exercises genuine-labelled, manipulated-labelled, mixed-signal, partial and inconclusive illustrative records through real FastAPI report routes. Each scenario checks exact source finding values/hashes, missing coverage, saved run context, unresolved artifact references, review lineage, unchanged source revisions, JSON and ZIP manifest hashes.

`reports/scenarios.py` seeds only explicitly requested test databases. All findings have `fixture=true`; placeholder evidence hashes do not represent preserved real media. The genuine/manipulated scenario names are fixture labels, not detector verdicts, measurements or a substitute for a real media/browser demonstration. No seed endpoint or automatic production seeding is enabled.

## Live browser verification

A clearly labelled test case was created through the actual UI, and `e2e/fixtures/valid.png` was preserved. Request analysis produced three saved findings: a completed PNG header inspection and two explicitly unavailable detector assessments. No model inference or authenticity verdict was claimed. The partial run was selected in Reports, revision 1 was saved, and Bhumi's review created revision 2. After browser refresh both revisions reopened and the first retained its original hash.

Revision 2 JSON and ZIP were downloaded through the UI. Independent checks verified exact JSON bytes against the ZIP member, manifest hash and byte size, the preserved file hash against the repository image, all three source finding hashes, and review lineage. The sample exports are in `samples/`. The print action opened a blocking dialog that could not be inspected; it was dismissed. PDF pagination is not yet verified.

## Print pagination rules

Print styles allow long findings and whole audit sections to span pages, repeat table headers, wrap long hashes/JSON, keep headings with following content and keep each audit-event block together. Screen controls, navigation and application height/overflow constraints are removed in print. The report uses white background, 10-point body text and 8.5-point technical values.

These are code-level pagination improvements, not a visually certified PDF. The native print check was interrupted and Safari reported the local backend unavailable during this attempt. Save-as-PDF page rendering and full visual inspection remain pending; no PDF was generated or approved in this check.
