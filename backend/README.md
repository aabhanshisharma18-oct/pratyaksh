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
- `POST /api/d1/probe-audio` — AASIST audio execution probe.
- `GET /api/capabilities` — implemented, loaded and evaluated state.

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

## Current boundary

- Implemented: bounded image analysis path and bounded audio execution probe.
- Not implemented: video, calibrated thresholds, D2 evidence intake, main D4
  dashboard integration, model training or a final authenticity verdict.
- Next evaluation work: permitted labelled controls, group-separated splits,
  threshold selection on development data and held-out error measurement.
