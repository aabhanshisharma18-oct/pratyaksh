# PRATYAKSH D4 user guide

Owner: Aadya
Last verified: 12 November 2026
Verified against repository base commit: `d585852`, with the D4 changes applied above it.

PRATYAKSH is a single-user multimedia-review prototype. It records separate findings and limitations. It does not certify that media is authentic or fake.

## 1. Prerequisites and install

Use Windows PowerShell first. The verified repository path is `C:\Users\HP\Pratyaksh`. Install Node.js with npm and Python 3.11 or newer. Model setup is optional for the UI and E2E harness because normal missing-model states remain explicit.

1. Open PowerShell and run:

   ```powershell
   cd C:\Users\HP\Pratyaksh
   npm ci
   python -m venv backend\.venv
   .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
   ```

   Expected: npm completes without vulnerabilities and Python installs the backend test/runtime packages.

2. For macOS/Linux, the repository documents `python3 -m venv backend/.venv` and `backend/.venv/bin/python`; this guide did not re-verify those platforms (`UNVERIFIED` platform note).

## 2. Start and check the services

1. In backend PowerShell:

   ```powershell
   cd C:\Users\HP\Pratyaksh\backend
   .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

   Expected: Uvicorn reports `http://127.0.0.1:8000`.

2. Check health:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/api/health
   ```

   Expected: `status` is `ok`; readiness fields honestly show which optional models/tools are present.

3. In frontend PowerShell:

   ```powershell
   cd C:\Users\HP\Pratyaksh
   $env:VITE_DEV_FIXTURE = 'false'
   $env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
   $env:VITE_D1_API_BASE_URL = 'http://127.0.0.1:8000'
   npm run dev
   ```

   Expected: Vite reports `http://127.0.0.1:5173/`. Open that URL and enter the workspace.

## 3. Environment variables

| Name | Required | Default | Example | Purpose |
| --- | --- | --- | --- | --- |
| `VITE_DEV_FIXTURE` | Optional | Not `true` | `true` | Enables committed illustrative fixtures only when `VITE_API_BASE_URL` is empty. |
| `VITE_API_BASE_URL` | Optional | Empty | `http://127.0.0.1:8000` | Enables persistent case, evidence, finding, note, activity and run API mode. |
| `VITE_D1_API_BASE_URL` | Optional | Falls back to `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Detection/run service URL. |
| `VITE_EVALUATION_BASE_URL` | Optional | Empty | `http://127.0.0.1:8000/evaluation-publication` | Base URL for `image.json`, `audio.json`, and `video.json`. |
| `VITE_EVIDENCE_API` | Optional, development only | `false` | `true` | Uses the separate port-8001 image-preservation demo. |
| `PRATYAKSH_DB_PATH` | Optional | `backend/data/pratyaksh.db` | `C:\data\pratyaksh.db` | SQLite case/run store. |
| `PRATYAKSH_CORS_ORIGINS` | Optional | `http://127.0.0.1:5173,http://localhost:5173` | `http://127.0.0.1:5173` | Comma-separated frontend origins. |
| `PRATYAKSH_EVIDENCE_DIR` | Optional | `backend/data/evidence` | `C:\data\evidence` | Storage for the separate D2 intake demo. |
| `PRATYAKSH_ENV` | E2E only | Empty | `test` | Must equal `test` before the deterministic worker can start. |
| `PRATYAKSH_E2E_STUB` | E2E only | Disabled | `1` | Selects deterministic findings. Startup fails if `PRATYAKSH_ENV` is not `test`. Never use for real review. |

Copy `.env.example` only as a starting point. It contains no secrets.

## 4. Fixture mode and API mode

Fixture mode uses committed, conspicuously labelled data from `fixtures/dev/`. It stores browser-only changes and performs no analysis. Start it with no API URL and `$env:VITE_DEV_FIXTURE='true'`.

API mode uses SQLite for case inventory, runs, events, findings, and reviewer notes. Set `VITE_API_BASE_URL`. Uploaded media remains a browser-session object; the case API registers metadata and a client-declared SHA-256 but does not preserve original bytes. Analysis copies are stored only for persistent runs. API mode takes precedence over fixture mode.

Open **Settings**. **Workspace** says `Persistent case inventory` in API mode or `Local single-user prototype` otherwise. **Fixture mode** states whether the build flag is enabled. **Backend connection** reports health.

## 5. Cases and evidence

1. Select **Cases**, then **New case**. Enter a title and context. Select **Create case**. Expected: a server-issued `CASE-YYYY-NNNNNN` opens.
2. Select **Add evidence**. Choose JPEG, PNG, MP4, WAV, or MP3, at most 50 MB in this dashboard flow. Expected: the browser calculates SHA-256 and registers metadata.
3. Open **Evidence**. Columns show the filename/ID/role, media type/size, latest run, four independent review channels, abbreviated SHA-256, registration time, and links. The case list's **Last activity** is the latest case, evidence, run, or note operational event.

Backend analysis bounds are stricter: static JPEG/PNG/WebP images up to 15 MiB and 20 million pixels with both dimensions at least 32; FFmpeg-decodable audio up to 25 MiB with at least one second decoded; FFmpeg-decodable video up to 50 MiB and 120 seconds, sampled at no more than 12 frames. A receipt/hash records what was submitted; it is not a chain-of-custody certificate.

## 6. Run analysis and read results

Open evidence and select **Request analysis**. Wait for the run history to become terminal. Findings stay in separate synthetic-media, tampering, integrity, and provenance channels. A raw confidence score is a model signal with its class/range/calibration status; it is not a probability that evidence is fake.

`Inconclusive` means the check ran but the project has no validated decision threshold. It is neither pass nor fail. Video uses bounded timestamp samples. The timeline marks examined, rejected, and unexamined samples; coverage is partial by design. Selecting a timestamp or region links the finding and viewer.

## 7. Reviewer annotations

In a finding card, choose `Reviewed` or `Questioned`, enter a note, then select **Add note**. API-mode notes persist with a server timestamp and self-declared author. Notes are append-only in the UI; there is no edit/delete control. They never rewrite the machine finding.

## 8. Status meanings

| Status/result | Meaning | Reviewer action | Must not be read as |
| --- | --- | --- | --- |
| `queued` | Accepted but not started. | Wait; investigate if it remains queued. | A result. |
| `running` | At least one requested check is active. | Wait and keep the page open if media is browser-only. | A result. |
| `completed` | Every requested check completed. | Read every finding, scope, and limitation. | Proof of authenticity or a pass. |
| `partial` | Some checks completed; another failed, timed out, was unsupported, or remained unexamined. | Use completed findings cautiously; inspect errors and coverage; retry eligible checks. | A pass. |
| `failed` | No requested check produced a completed result. | Read the error and retry only when offered. | Evidence of manipulation or cleanliness. |
| `unsupported` | The adapter cannot examine this input/configuration. | Use a supported format or method. | A negative finding. |
| `cancelled` | Work stopped before completion. | Start a new run if still required. | A result. |
| `inconclusive` | Finding result: execution completed without a validated decision. | Review the observation and limitations. | Pass, fail, authentic, or fake. |
| `unexamined` | Coverage/check state: planned material was not examined; the aggregate run is partial. | Identify the gap and obtain more coverage if needed. | A pass or clean sample. |
| `not_applicable` | A finding/check does not apply, such as no comparison reference. | Record why and use another appropriate method. | A clean result. |

## 9. Retry

**Retry (new run)** creates a new child run and carries completed checks forward. Only failed or unfinished checks execute again. The parent's status, findings, and events remain unchanged; history shows both attempts and `Retry of …` lineage.

## 10. Evaluation publication

The Evaluation view reads three JSON publications and validates the complete contract before showing metrics. `unavailable` means no URL/file was published (not zero results). `invalid` means retrieval or schema validation failed; no partial metrics render. `loaded` shows dataset, model version, threshold, run date, metrics, coverage, limitations, and self-declared publisher.

The dashboard cannot publish. The evaluation owner produces files with the scripts documented in `backend/evaluation/README.md`, places them at `VITE_EVALUATION_BASE_URL`, then the reviewer reloads the page or uses **Retry** on an invalid card. The screen does not claim real-world accuracy, calibration, universality, or authenticity.

## 11. Accessibility

Use `Tab`, `Shift+Tab`, `Enter`, and `Space` for controls. `Ctrl+K` focuses global search. Image viewer: `+`, `-`, and `0` zoom. Audio/video: Space play/pause; arrows seek; Shift+arrows fine seek; `,`/`.` step; `[`/`]` mark an interval; `L` loops; Escape clears. Chromium was exercised at 320 px and normal desktop width. Browser zoom can be used, but only Playwright Chromium was tested.

## 12. Known limitations

- Video is sampled, not exhaustive. Unexamined samples and partial coverage are expected.
- Models and thresholds are candidates; successful outputs remain inconclusive until held-out evaluation supports a decision.
- Case inventory does not preserve uploaded originals. The separate D2 image-intake demo is not the main dashboard flow.
- Single-user loopback prototype; no authentication or authorization. Analyst and publisher identities are self-declared.
- SQLite operational logs are not tamper-evident audit trails or chain-of-custody records.
- Axe found serious color-contrast failures in current light/dark styling. The D4 suite fails on critical axe violations and retains this serious issue for visual-system remediation.
- Only Playwright Chromium was verified. Firefox, WebKit, macOS, and Linux are `UNVERIFIED`.
- No tests are marked `test.fixme` in the D4 suite.

## 13. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError: detector` | Start Uvicorn from `backend` as `main:app`, or use `--app-dir backend`; do not use `backend.main:app` with the backend's local imports. |
| Port already in use | Stop the existing process or choose another port and update both Vite URLs and CORS. The E2E harness uses isolated ports 15173/18000. |
| Backend health fails | Activate the venv, install `backend/requirements-dev.txt`, and inspect the Uvicorn traceback. |
| No cases persist | Confirm `VITE_API_BASE_URL` before starting Vite and check **Settings**. |
| Request analysis is disabled | Re-add the file; the case API does not restore media bytes to the browser after reload. |
| Run fails with missing model | Read the explicit error/capability state. Install optional model files only through documented setup scripts. |
| Evaluation says unavailable | Set `VITE_EVALUATION_BASE_URL` and publish all intended JSON files. Do not interpret unavailable as zero. |
| E2E server refuses to start | Set both test variables through Playwright; `PRATYAKSH_E2E_STUB=1` alone is deliberately rejected. |

Run browser tests with `npm run test:e2e`. There is no CI configuration in this repository, so no E2E CI job was added.
