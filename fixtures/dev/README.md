# Development fixtures

These records are fictional and exist only to exercise dashboard states. Every
payload is wrapped with `__PRATYAKSH_FIXTURE_PAYLOAD__`, every validated record
has `fixture: true`, and no number is a forensic conclusion or product claim.
The SHA-256 strings are fictional identifiers and are not claimed to be hashes
of any file. No media files, real people, organizations, brands or datasets are
represented.

The dashboard loader may import these files only when `VITE_DEV_FIXTURE=true`
and API mode is not configured. Production builds must be checked to ensure the
marker is absent. The schemas live in `backend/contracts/dashboard-*.schema.json`.
