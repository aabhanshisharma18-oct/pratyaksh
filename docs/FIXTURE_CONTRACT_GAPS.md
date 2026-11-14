# Development fixture contract gaps

This audit compares the dashboard's frontend Zod contract in
`frontend/src/model.ts` with the teammate-owned D1 JSON Schemas in
`backend/contracts/d1-finding.schema.json` and `d1-run.schema.json`. Those
contracts are intentionally unchanged. Development fixtures follow the additive
dashboard 1.1 schemas because the UI needs conservative, multi-channel states
without producing operational verdicts.

## Finding differences

| Concern | Frontend dashboard | D1 finding 1.0 | Fixture decision |
| --- | --- | --- | --- |
| Category | synthetic media, tampering, integrity, provenance | `synthetic_media` only | Dashboard 1.1 multi-channel enum |
| Execution status | queued, running, completed, failed, unsupported, not_applicable, cancelled | queued, running, completed, failed, cancelled, unavailable | Keep frontend vocabulary; `unsupported` is explicit and never clean |
| Result | indicators_detected, no_indicators_detected, inconclusive, null | genuine, synthetic, inconclusive, not_applicable | Never use genuine/synthetic verdicts; null represents no assessment |
| Review status | unreviewed, accepted, questioned | unreviewed, accepted, rejected, needs_review | Keep non-destructive dashboard review vocabulary |
| Score positive class | Method-specific string | literal `Deepfake` | Method-specific, with raw-score and uncalibrated labels required |
| Location | Previously nullable time range | Any object or null | Add a discriminated union for time ranges, points and normalized regions |
| Structured details | Needed for integrity and provenance | Not allowed by `additionalProperties:false` | Add strict category-specific dashboard details |
| Error | Needed on failed checks | Run errors only | Add nullable finding error with code, message and retryable |
| Schema version | 1.0 | 1.0 | Add dashboard finding 1.1; do not replace D1 |
| Extra fields | Zod previously stripped unknown fields | JSON Schema rejects them | Dashboard 1.1 is strict in both Zod and JSON Schema |

## Run differences

| Concern | Dashboard need | D1 run 1.0 | Fixture decision |
| --- | --- | --- | --- |
| Finding reference | Multi-channel dashboard finding | References D1 synthetic-only finding | Reference dashboard finding 1.1 |
| Run status | completed, partial, queued, running, failed, cancelled | Same plus unavailable | Omit unavailable; unsupported is realized at finding level |
| Coverage | Examined/rejected/unexamined counts and sample states | Free-form object or null | Strict coverage object with internally consistent counts |
| Errors | code, message, retryable | retryable optional | Require retryable for fixture clarity |
| Fixture marker | Required on every fixture record | No run-level fixture field | Require `fixture: true` |
| Configuration | Fixture method identity | arbitrary non-empty string | Require fixture-labelled configuration version |

## Evidence and evaluation

The production case-evidence schema cannot accept a `fixture` property because it
is strict. The additive dashboard case-evidence schema therefore reuses its field
semantics while requiring `fixture: true`, `hash_source: client_declared`,
`preserved: false`, and `preserved_evidence_id: null`.

The evaluation scripts emit measured-result envelopes, but development fixture
files require an explicit fixture marker, modality status (including video not
evaluated and no-measurement states), failures, and strict separation from real
pilot documents. The additive dashboard evaluation 1.1 schema models that
presentation contract. It never defines a combined authenticity score.

## Safety boundary

Fixtures are fictional UI-development records, not D1 API responses and not real
evaluation results. They load only when `VITE_DEV_FIXTURE=true` and API mode is
off. Missing credentials remain neutral; an integrity mismatch means only that
bytes differ from a declared reference. Neither state establishes authenticity,
manipulation, attribution, preservation, or chain of custody.

## Job-status additions requiring contract-owner confirmation

The dashboard run 1.1 contract now accepts optional `attempt`, `retry_of`,
`origin`, `requested_channels`, `status_reason`, and `configuration_version`
fields. They are dashboard-only retry and presentation metadata; the teammate-
owned D1 contracts remain unchanged. Existing fixtures remain valid without
these fields.

The D1 status `unavailable` is adapted to dashboard `unsupported` with
`status_reason: capability_unavailable`, while the original value is retained
as `backend_status`. This is an explicit vocabulary mapping, not an assertion
that the two meanings are identical. Unknown backend statuses are displayed as
failed with `unknown_backend_status` and are never treated as a result.

Retry is a new immutable run: it references the prior run with `retry_of`,
increments `attempt`, and does not copy findings, errors, artifacts, coverage,
or lifecycle timestamps. Partial retries are full-channel runs in this phase.

### Backend proposal (out of scope here)

A production service should provide immutable run create/list/get endpoints,
idempotency for duplicate submissions, status/cancellation transitions, and
polling or SSE updates. It should retain the uploaded evidence under an explicit
preservation policy before advertising retry availability. The current D1
analysis endpoints are synchronous and the case service retains inventory
metadata only, so API mode has no historical run list after refresh. No client
simulation is used as fallback after a server error.
