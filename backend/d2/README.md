# Pratyaksh D2 Evidence Authentication

D2 is a single-user forensic preservation, metadata, and bounded classical manipulation-analysis prototype. It does not detect deepfakes or prove authenticity or tampering.

## Setup

Use Python 3.11 or newer. From the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
```

Install ExifTool and FFmpeg/ffprobe on `PATH`. Metadata records explicit tool errors when an external tool is unavailable. Configuration variables are `PRATYAKSH_D2_ROOT`, `PRATYAKSH_D2_DB`, and `PRATYAKSH_DEMO_IDENTITY`; none contains a secret.

## Run and demo

`make demo` generates seeded controls and starts the integrated FastAPI service. On Windows without Make:

```powershell
python -m backend.d2.samples.generate
cd backend
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/d2`; OpenAPI is at `/docs`. Generate samples independently with `make d2-samples` and run tests with `make d2-test`.

## Architecture

- `intake/`: streamed, atomic intake and server-generated IDs
- `integrity/`: independent SHA-256 verification
- `derivatives/`: separate artifact tree and provenance records
- `audit/`: append-only, hash-chained events
- `metadata/`: ExifTool, ffprobe, and Pillow snapshots
- `analysis/`: uniform structured copy-move and video-continuity methods
- `api/` and `ui/`: FastAPI/OpenAPI and Jinja2 operator workspace
- `export/`: self-describing ZIP package and SHA-256 manifest
- `samples/`, `tests/`, `docs/`: reproducibility, verification, interpretation

SQLite uses WAL mode and database triggers prohibit audit updates/deletes. Original filenames are descriptive metadata only; storage paths use Evidence IDs. Original files are finalized with fsync/atomic rename and made read-only. Derivatives and exports re-verify their parent first.

## API summary

- `POST /api/d2/evidence`, `GET /api/d2/evidence/{id}`
- `POST /api/d2/evidence/{id}/verify` and `/metadata`
- `POST /api/d2/evidence/{id}/analysis/copy-move`
- `POST /api/d2/evidence/{id}/analysis/video-continuity`
- `GET /api/d2/derivatives/{id}`
- `GET /api/d2/audit`, `POST /api/d2/audit/verify`
- `POST /api/d2/evidence/{id}/export`

See `docs/Limitations_and_Interpretation_Guide.md` and `docs/REQUIREMENTS_TRACEABILITY.md` before interpreting results.
