# Automated multimedia demonstration case

`backend/scripts/import_automated_demo.py` imports the supplied
`Pratyaksh-Automated-Demo.zip` into the same persistent case, evidence,
provenance, audit, and reporting stores used by the web application.

## What the importer proves

- all nine expected files are present and match their pinned SHA-256 values;
- the original bytes are preserved under their server-computed hashes;
- the exact-copy pair is detected by identical SHA-256 values;
- candidate visual relationships are measured by the existing dHash and
  SIFT/RANSAC provenance workflow;
- a report revision records the evidence inventory, measured findings,
  coverage gaps, limitations, and next steps.

## What it does not prove

Words such as `synthetic`, `generative`, and `copy-move` in filenames are
supplier-provided test labels. They are not converted into detector verdicts.
The importer does not claim that an image, voice, or video is fake. Dedicated,
validated modality detectors must be run separately before such a conclusion.

## Import and open the case

From the repository root:

```bash
backend/.venv/bin/python backend/scripts/import_automated_demo.py \
  /Users/aabhanshisharma/Downloads/Pratyaksh-Automated-Demo.zip
```

Start the backend and API-connected frontend:

```bash
backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Open the generated case in **Cases**. Its preserved media is available in
**Evidence**, measured links in **Provenance**, explanatory limitations in
**Explainability**, intake events in **Audit**, and the saved revision in
**Reports**.
