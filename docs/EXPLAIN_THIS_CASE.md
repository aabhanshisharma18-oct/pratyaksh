# Explain this case

The XAI Dashboard can generate a short, cited briefing of a case's saved records.
It presents key findings, open questions and suggested next steps. The briefing
is an AI-generated draft for investigator review, separate from forensic findings.

## Backend setup

Save the Gemini provider key in Prune. On the backend machine, export a new Prune
key in the shell that starts FastAPI. Do not paste keys into chat or source code.
The backend reads environment variables; it does not automatically load `.env`.

```sh
export PRUNE_API_KEY='your-new-prune-key'
export PRATYAKSH_BRIEFING_MODEL='gemini-3.5-flash-lite'
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Use a model with available free quota in the project owning your Gemini key.
No billing setup or automatic paid fallback is added. Prune and provider quotas
still apply. A missing key or quota error is shown beside the briefing button;
the saved examination records remain usable.

The frontend needs `VITE_API_BASE_URL` pointing at the case backend, as in the
existing case workspace. Open a saved case in the XAI Dashboard and click
**Explain this case**. Browser-only fixture cases cannot request an explanation.

## What leaves the machine

`POST /api/cases/{case_id}/briefing` takes no media or client-supplied findings.
The server builds an allowlisted snapshot from the case repository, run history
and latest saved case provenance report. The request includes evidence and run
IDs, observation text, method, scope, score semantics, execution/result states,
bounded limitations, and numeric relationship support. It excludes original
media, filenames, hashes, case title/description, extracted metadata, analyst
identities, notes, arbitrary detail payloads and artifact URLs.

Finding text itself can contain sensitive information. The UI discloses that
recorded text goes to Prune and its AI provider. Use synthetic case data for
the free-tier demonstration. This is not a local language model.

## Citations and limits

Every generated item must cite an ID from the supplied case snapshot. The
backend validates the JSON format and rejects unknown IDs and generated URLs.
The frontend resolves links from server-owned evidence/run/finding IDs, rather
than accepting links from the model. An image comparison link opens the exact
saved provenance report and relationship, with matching regions enabled.

Failed and unfinished runs, inconclusive results, absent saved checks, and
opposing outcomes from the same method are surfaced as deterministic cautions.
These are shown even when the AI omits them. Different methods are not treated
as directly comparable scores or combined into an authenticity verdict.

Citation validation establishes that a referenced record exists; it does not
prove that the model's wording follows from that record. Investigators must
inspect the source record, limitations and comparison before relying on a draft.
In particular, a geometric match alone cannot establish extra text or editing
order. Those statements require separately recorded evidence.

The server rejects oversized snapshots instead of silently dropping findings.
It does not retry paid requests or automatically switch providers. The Prune
request disables gateway caching. A bounded, in-memory ten-minute cache reuses
only an identical case snapshot, prompt version, configured model and key.
Changed records invalidate it. Changes during generation reject the stale
briefing. The UI hides an existing draft when its displayed record set changes.
Drafts are not inserted into machine findings or saved forensic reports.

The existing local prototype's self-declared investigator identity and API
access model are unchanged. Production deployment needs the same case access
controls as the rest of the application.

## Validation and demo

```sh
python -m pytest backend/tests/test_case_briefing.py -q
npm test
npm run build
```

Backend tests use a simulated provider and temporary case records. A live
Prune/Gemini check requires the server-side key; no key is bundled with this work.
For the presentation, finish the case checks, open XAI Dashboard, generate the
briefing, and click an image comparison or voice finding to inspect its proof.

## Live connection check

On 14 November 2026, the running local backend successfully generated all three
briefing sections through Prune and Gemini for a clearly labelled synthetic
connection-test case. The dashboard displayed the live result and its citation
opened the correct saved finding. No real media or private case data was used.
Prune requests use the deployed `/v1/chat/completions` compatibility route;
the Gemini-specific URL shown in onboarding was not usable in this check.

## Updated navigation after the team pull

The team consolidated the XAI workflow into **Review & Report**. Open a case
and select Review & Report to use Explain this case. The old `/explainability`
route redirects to the consolidated review workflow.
