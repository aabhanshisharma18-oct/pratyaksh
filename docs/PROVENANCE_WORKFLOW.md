# Provenance workflow

Open /#/provenance. Choose a case ID, title and self-declared analyst, upload related files, and analyze their relationships. The existing operational case activity API is separate from this provenance store.

## Local setup

From the repository root, install the Python requirements:

    backend/.venv/bin/python -m pip install -r backend/requirements-provenance.txt

Install ExifTool and FFmpeg/ffprobe through the OS package manager. On macOS:

    brew install exiftool ffmpeg

Start the existing detection service, then Vite:

    PRATYAKSH_SBI_PILOT=still-images backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8011
    npm run dev

The local Vite configuration reads VITE_D1_API_BASE_URL from .env.local.

## Supported examination

JPEG, PNG, static WebP and HEIC images (with pillow-heif installed) support SHA-256 duplicate grouping, dHash candidate distances, SIFT/RANSAC matching, normalized region bounds and aligned difference overlays. The bounded batch also performs an expanded region search when global hashes differ, because crops can defeat whole-image hashes.

WAV and MP3 support preservation, exact duplicates, ffprobe metadata, credential reading where supported by the SDK, and optional AASIST signals. Video matching and PRNU are future work.

ExifTool extracts file-provided source fields. Metadata agreements are clues rather than proof of a specific device or owner.

C2PA reading uses the official Python SDK with remote-manifest and OCSP fetching disabled. Signature validity, content binding, certificate-policy errors and signer trust remain separate. An absent manifest is neutral. See the [C2PA Python context documentation](https://github.com/contentauth/c2pa-python/blob/main/docs/context-settings.md).

## Preservation and hash anchors

The separate store is backend/data/provenance, configurable through PRATYAKSH_PROVENANCE_DIR. Original files are keyed by SHA-256 and made read-only. SQLite stores case context, report snapshots, file records, graph edges and provenance events.

Each event hashes its canonical payload, which includes the previous event hash. Transactions serialize sequence allocation and report commits. Identical files share an original blob while retaining separate intake records and filenames. Files already present are re-hashed before reuse.

A retained external anchor is needed to detect complete privileged rewriting of a local chain. The UI accepts an anchor from an exported report. Filesystem read-only permissions and local hash chaining provide bounded protections.

Each report's report_sha256 covers the JSON payload excluding that field, encoded as UTF-8 using Python JSON with sorted keys, compact separators and ensure_ascii=False. Download the saved server export to preserve numeric representation. For example:

    import hashlib, json

    with open("saved-report.json", encoding="utf-8") as stream:
        report = json.load(stream)
    expected = report.pop("report_sha256")
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == expected

The PDF includes this payload hash and the log anchor, together with case details, file hashes, the connection graph, per-link evidence, metadata, credential results, detector signals and limits, a provenance activity excerpt and an unsigned signature block. PDF generation first verifies preserved originals and chain consistency. It supplies no legal certification or digital signature.

Detector execution saves a new report revision and keeps the previous snapshot. Failed and unsupported model checks remain visible as supporting findings.

## Demonstration data

The local eight-file folder contains synthetic reference images, a JPEG re-save, a self-captured application screenshot and an independent AI-generated scene. The five initial photo-like images are AI-generated. The generative crop and edits can change pixels beyond their intended regions. Ground-truth labels describe how the files were created and are never read by the analysis engine.

A separate local phone-photo case uses the user-supplied IMG_8568.HEIC. Its original bytes are preserved, with controlled crop, text and JPEG derivatives. This private demo folder is excluded from Git. Evaluate identity and generator generalization separately from these functional demos.


## Complete examination and handover

1. Upload 2–12 files under a case ID (15 MiB each; 60 MiB total). The originals are preserved before the saved analysis is returned. Source files are never edited.
2. Inspect exact copies, supported geometric relations and weak metadata agreements using the connection-type filter. Click nodes to inspect files and edges to inspect their supporting evidence. Parallel evidence types have separate curved links.
3. Inspect aligned difference overlays. Red residuals are differences in the matched overlap, not an automatic declaration that an object was forged.
4. Add files to the saved analysis, up to the same batch limits. This recomputes connections in a new snapshot; earlier snapshots remain available. Existing detector records are carried forward for the unchanged original bytes.
5. Save a reviewer interpretation for the whole analysis, a file or a connection. The author is self-declared, not authenticated. Notes are distinct from machine findings, hash-anchored in a new immutable snapshot, and included in the PDF and JSON. Notes retain their originating analysis reference when a later extension changes pair numbering.
6. Verify originals and the chain, optionally against an externally retained anchor. Recording stops if existing chain entries or retained saved-analysis anchors are inconsistent.
7. Download the PDF, raw JSON or **Evidence package**. The ZIP contains hash-keyed original files, report.json, report.pdf, activity.json, manifest.json, README.txt and verify.py. The UI displays the manifest hash: retain it independently before handover.
8. Extract the ZIP and run the verifier with Python 3.9 or newer, without installing dependencies:

       python3 verify.py --expected-manifest YOUR_INDEPENDENTLY_RETAINED_MANIFEST_SHA256

   It checks the manifest against that external hash, packaged artifact hashes, canonical report hash, file inventory, event chain and the saved analysis anchor. It exits nonzero on failure. Without an external hash it checks internal consistency only. Neither a checksum nor this unsigned package proves authorship or authenticity. Review verifier source before running downloaded code.
9. Use **Resume last saved analysis** after a browser reload, or **Saved analyses** for the selected case. Only the last analysis identifier is kept in browser storage; originals and immutable snapshots stay in the local backend store.

### API additions

All paths below start with `/api/d1/provenance`:

- POST `/analyze` — multipart files plus case_id, case_title, analyst.
- GET `/reports?case_id=...` — newest 100 snapshots for that case.
- GET `/reports/{id}` and `/reports/{id}/export` — typed snapshot and byte-preserving JSON export.
- POST `/reports/{id}/extend` — multipart additional files; returns a new comparison snapshot.
- POST `/reports/{id}/notes` — JSON author, text (maximum 4,000 characters), optional scope_id; returns a new reviewed snapshot.
- GET `/reports/{id}/images/{file_id}` and `/preview` — verified original and browser-friendly image preview.
- POST `/reports/{id}/images/{file_id}/verify` — supplied-file hash comparison.
- POST `/reports/{id}/images/{file_id}/signals` — supporting detector records in a new snapshot.
- GET `/reports/{id}/relationships/{edge_id}/difference` — aligned residual visualization.
- GET `/reports/{id}/audit` — separate provenance log, with scope and limitations.
- POST `/reports/{id}/verify` — original and chain verification; optional retained_anchor query parameter.
- POST `/reports/{id}/pdf` and `/bundle` — integrity-gated PDF and portable evidence package.

### What this release establishes

This is a local hackathon prototype for image-file relationships and evidence handover. Exact duplicate grouping is cryptographic. Region matching is an investigative lead with geometric evidence. Metadata and credential assertions are shown with their validation scope; they do not identify the camera owner. There is no automatic original-uploader discovery, WhatsApp forwarding trace, editing-order reconstruction, PRNU device identification or video relationship matching. Supporting detector benchmark accuracy is separate from provenance functionality. Multi-user authentication, signed external timestamping, encrypted storage, backup/retention policy and agency deployment hardening are outside this local release.

### Regression checks

    PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m unittest discover -s backend/tests -p test_provenance.py -v
    PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m unittest discover -s backend/tests -p test_cases_api.py -q
    npm test
    npm run build

Provenance tests exercise duplicate grouping, real geometric crops, unrelated controls, untrusted metadata, malformed input, native HEIC preservation, immutable detector/reviewer revisions, adding files, exported numeric/hash fidelity, supplied-original verification, chain mutation/truncation, PDF integrity gates, offline bundle verification and changed-package detection. The private phone-photo demonstration is a functional walkthrough, not a statistical accuracy benchmark.
