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
