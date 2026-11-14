# Aabhanshi — D1 Days 2-3 candidates

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python setup_day23_models.py
python -m unittest discover -s tests -v
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/docs` to test the APIs:

- `POST /api/d1/analyze-image` — UniversalFakeDetect image candidate.
- `POST /api/d1/analyze-video` — bounded timestamp sampling with per-frame UniversalFakeDetect signals.
- `POST /api/d1/analyze-face-forgery` — optional SBI face-forgery research candidate.
- `POST /api/d1/probe-audio` — AASIST audio execution probe.
- `GET /api/capabilities` — implemented, loaded and evaluated state.
- `POST /api/cases` and `GET /api/cases` — persistent case records.
- `POST /api/cases/{case_id}/evidence` — inventory metadata and a
  client-declared hash; the file is not uploaded or preserved.

## Case store configuration

The case API uses SQLite from the Python standard library and initializes its
schema idempotently. By default the database is `backend/data/pratyaksh.db`.
Override it with `PRATYAKSH_DB_PATH`:

```powershell
$env:PRATYAKSH_DB_PATH = "C:\data\pratyaksh.db"
```

The Vite development origins `http://127.0.0.1:5173` and
`http://localhost:5173` are allowed by default. Set a comma-separated
`PRATYAKSH_CORS_ORIGINS` value to replace that list. Start the frontend with
`VITE_API_BASE_URL=http://127.0.0.1:8000` to enable API mode. Without that value,
the frontend remains an explicitly labelled localStorage prototype.

`X-Analyst-Name` is optional and self-declared; it is not authenticated. The case
event table is an operational log, not a tamper-evident audit trail. D2 file
preservation remains unimplemented.

The setup script checks out pinned official source revisions and verifies the model
checkpoints. Model files and uploaded evidence stay local and are ignored by Git.

## Result meaning

Both candidates return raw model signals. They have not been evaluated on the
Pratyaksh held-out dataset, have no project threshold and must not provide a final
real/fake verdict. Completed image and audio executions therefore remain
`inconclusive`.

The image endpoint records the input hash, dimensions, model/checkpoint identity,
preprocessing version, runtime and limitations. It discards the uploaded image.
The audio endpoint records the input hash and probe metadata, and discards the
uploaded audio. Neither endpoint claims D2 preservation or chain of custody.

## Optional face-forgery research candidate

The SBI candidate is intended to address face manipulation such as face swaps,
which the whole-image AI-generation model is not designed to specialize in. SBI
is restricted to noncommercial research use. Read the model card and official
licence before accepting it, then install and verify the local model files:

```bash
python -m pip install -r requirements-face-research.txt
python setup_face_research_models.py --accept-sbi-research-license
```

Restart the API and use `POST /api/d1/analyze-face-forgery`. Its output is a raw,
uncalibrated research signal, not a real/fake verdict. Accuracy must be measured
on labelled development and held-out test data before selecting a threshold.

## Video baseline

`POST /api/d1/analyze-video` accepts an FFmpeg-decodable video up to 50 MiB and
120 seconds. FFprobe supplies the first video stream's presentation timestamps.
The service selects at most 12 timestamps near the centres of two-second sampling
bins, decodes those frames, and applies the same whole-image candidate used by the
image endpoint. The response retains each examined timestamp, rejected samples,
coverage, and separate arithmetic-mean and maximum raw frame signals.

This is not a temporal, motion-consistency, face-swap, lip-sync or audio-visual
detector. The summaries have no validated video threshold and every successful
video result remains `inconclusive`. Video-specific held-out evaluation is still
required before enabling any decision label.

## Current boundary

- Implemented: bounded whole-image analysis, bounded timestamp-sampled video
  analysis, optional bounded face-forgery research analysis, and bounded audio
  execution probe.
- Not implemented: video-specific calibrated aggregation, calibrated thresholds, D2 evidence intake, main D4
  dashboard integration, model training or a final authenticity verdict.
- Next evaluation work: permitted labelled controls, group-separated splits,
  threshold selection on development data and held-out error measurement.

## Evaluation foundation

The version 1.1 evaluation manifest records manipulation type and the documented
basis for every ground-truth label. The evaluator reports false-negative and
false-positive rates, ranking metrics, and manipulation-specific performance.
Threshold selection is restricted to the development split. See
`evaluation/README.md`; never commit restricted evaluation media.

## Combined image and audio scan

`POST /api/d1/scan` accepts multipart fields `file`, `evidence_id`, and
`media_type` (`image` or `audio`). Image scans run UniversalFakeDetect, the optional
SBI face-forgery candidate, and file inspection. Audio scans run AASIST and file
inspection. The response contains a shared run ID, input SHA-256, individual findings,
and an overall review state. The summary is inconclusive when at least one check
completed, and unavailable otherwise. The model score and file properties have
different meanings and remain separate until a fusion rule has been validated.

Successful SBI checks also return `face_analysis`, containing the decoded image
dimensions, per-face crop boxes in pixel coordinates, and raw face-forgery scores.
A completed search with no detected faces returns `execution_status: no_face` in
`face_analysis` and no score. Missing SBI files produce an unavailable finding
while the other checks continue. The Image workspace shows selectable face scores
and crop boxes. Checkpoint files remain local under the research licence.

For the local workbench, start this backend on port 8000 and use
`VITE_D1_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --port 5173`.
Add a supported image or audio file, open it in the workbench, and choose
**Request analysis**. Use browser intake for audio. The workspace keeps the
latest result per evidence item for the current session. Saving a report revision
captures its findings.
