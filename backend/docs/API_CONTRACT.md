# D1 API contract

Contract version: `1.0`

The canonical finding schema is `contracts/d1-finding.schema.json`; the complete
modality-run envelope is `contracts/d1-run.schema.json`.

## Endpoints

- `GET /api/health` separates service availability, local model files and loaded
  model state.
- `GET /api/capabilities` publishes implemented, loaded and evaluated state for
  image, video and audio separately.
- `POST /api/d1/analyze-image` accepts a bounded static image and returns one
  traceable, inconclusive synthetic-media finding.
- `POST /api/d1/analyze-face-forgery` detects faces with YuNet and applies the
  optional SBI research candidate to each crop. The maximum face signal is
  reported without a final verdict.
- `POST /api/d1/probe-audio` accepts bounded FFmpeg-decodable audio and returns an
  AASIST execution-probe record. It is not yet a canonical finding.
- `POST /api/cases` creates a persistent case with a server-issued identifier.
- `GET /api/cases` lists cases newest first with optional `q`, `status`, `limit`
  and `offset` parameters.
- `GET /api/cases/{case_id}` returns one case plus evidence counts by media type.
- `POST /api/cases/{case_id}/evidence` registers metadata and a client-declared
  hash as an inventory link. It does not upload or preserve the file.
- `GET /api/cases/{case_id}/evidence` lists inventory links, optionally filtered
  by `role` or `media_type`.

Missing models, invalid files, failed decoding and failed inference never become
genuine results.

## Persistent case inventory

Case responses follow `contracts/case.schema.json`. IDs have the form
`CASE-<UTC year>-<six digit sequence>` and are allocated transactionally by the
server. New cases start in `Open` status. `created_by` is copied from the optional
`X-Analyst-Name` header, defaulting to `Demo analyst`. There is no authentication
in this contract, so the value is self-declared and every response sets
`created_by_verified` to `false`.

Evidence responses follow `contracts/case-evidence.schema.json`. The endpoint
stores filename, media type, role, size and a client-declared SHA-256 value only.
It always returns `hash_source: "client_declared"`, `preserved: false`, and
`preserved_evidence_id: null`. A repeated hash is allowed and reported through
`duplicate_hash_of`; it is a warning, not proof that two files are identical.

`case_events` records `case.created` and `evidence.registered` operational events.
It has no application update or delete path, but it is an ordinary SQLite log,
not a cryptographically protected or tamper-evident audit trail and not a chain
of custody.

## Evidence identity

The image endpoint creates a `LOCAL-` identifier and does not claim preservation
or custody. D2 integration will supply a preserved evidence ID and approved working
copy. D1 must never overwrite the original.

## Score semantics

The whole-image score is the UniversalFakeDetect sigmoid synthetic-class output.
The face-forgery score is the SBI fake-class softmax output for the highest-scored
detected face. The audio score is the AASIST spoof-class softmax output. None is a
calibrated probability that evidence is fake. Until held-out evaluation freezes
a threshold, every successful result remains `inconclusive`.

## Processing bounds

- Images: JPEG, PNG or static WEBP; 15 MiB; 20 million decoded pixels; minimum
  dimension 32 pixels.
- Audio: 25 MiB; any FFmpeg-decodable format; mono 16 kHz conversion; 30-second
  decode bound; minimum one second; silence/low-energy rejection.
- AASIST evaluates the first 64,600 decoded samples (about 4.04 seconds), repeating
  shorter accepted audio to the model input length.

## Future contract work

- D2 file intake, preservation and assignment of `preserved_evidence_id`.
- Authentication and authorization replacing the self-declared analyst header.
- Tamper-evident operational audit storage and retention controls.
- Asynchronous creation, status, timeout and cancellation.
- Video frame and audio segment locations in original-timeline milliseconds.
- Evaluated threshold versions, calibration state and aggregation identity.
