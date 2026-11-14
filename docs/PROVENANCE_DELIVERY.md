# Provenance delivery

This batch delivers the provenance and source-attribution implementation from
the local full application at `~/Documents/pratyaksh`. It includes preservation,
metadata and offline Content Credentials inspection, case comparisons, saved
reports, PDF and independently verifiable package exports, the provenance
interface, synthetic public fixtures, tests and benchmark tooling.

## Shared integration still required

The publishing repository is a partial application. This delivery does not
include the other owners' remaining files or replace shared application wiring.

- The backend application entry point must register `provenance.router`.
  The optional detector-enrichment endpoint calls `main.scan_evidence`.
- The frontend application must register `ProvenanceLab` and supply its existing
  shared model, internationalization, PageHeading component and case API client.
- Case and run routers, video sampling and provenance requirements are already
  published. FFmpeg/FFprobe and optional ExifTool are external tools.
- The LightGlue pilot requires its separately obtained checkout and weights;
  it does not replace the live matcher.
- Historical validation statements in the copied release and benchmark records
  describe the full source application and their stated datasets, rather than
  a complete build of this partial publishing checkout.

## Verification

Install `backend/requirements-provenance-dev.txt` in a Python environment, then
run `python -m pytest backend/tests/test_provenance.py -q` from the repository
root. These tests construct their own API application and temporary storage.

The full source application's current frontend passed 109 tests and a production
TypeScript/Vite build during this delivery. A complete frontend build in the
publishing repository requires the remaining shared frontend files.

Metadata and visual relationships are investigative observations. They do not
establish original authorship, capture order or file authenticity. Private phone
photos, generated evidence packages, model weights, databases and local secrets
are excluded from this delivery.
