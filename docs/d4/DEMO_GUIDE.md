# PRATYAKSH D4 demonstration guide

Owner: Aadya
Last verified: 12 November 2026
Verified against repository base commit: `d585852`, with the D4 changes applied above it.

## Purpose and 12-minute plan

This walkthrough is for reviewers assessing traceability, honest status semantics, accessibility, and recovery—not detector accuracy.

| Time | Segment |
| --- | --- |
| 0:00–1:00 | Scope and limitations |
| 1:00–3:00 | Create case and add evidence |
| 3:00–5:00 | Run analysis and open a finding |
| 5:00–6:30 | Add reviewer note |
| 6:30–8:00 | Partial/failed status and retry lineage |
| 8:00–9:30 | Video sampling and coverage |
| 9:30–10:30 | Evaluation states |
| 10:30–12:00 | Refresh restoration and questions |

## Pre-demo checklist

1. From `C:\Users\HP\Pratyaksh`, install dependencies with `npm ci` and the backend command in the user guide. Expected: both complete.
2. Reset a dedicated database:

   ```powershell
   .\backend\.venv\Scripts\python.exe backend\scripts\seed_d4_demo.py --database backend\data\d4-demo.db
   ```

   Expected: one JSON line naming `CASE-2026-000001` and `EVID-D4-IMAGE`. Running the same command again prints the identical line.
3. Set `$env:PRATYAKSH_DB_PATH=(Resolve-Path backend\data\d4-demo.db)` and start backend/frontend using the user guide. Do not set the E2E stub for a real-evidence demonstration.
4. Check `/api/health`, open **Settings**, and confirm `Persistent case inventory`.
5. Add `e2e\fixtures\valid.png` and verify one full run works. If optional models are absent, use the explicit offline fixture fallback below; do not imply inference ran.
6. Use Playwright Chromium at 100% browser zoom and at least 1280×720. Close notifications and unrelated tabs. `UNVERIFIED`: projector-specific scaling.

## Scripted walkthrough

1. Select **Cases → New case**. Enter `Reviewer demonstration` and select **Create case**. Say: “A server-issued case ID and self-declared creator are recorded.”
2. Select **Add evidence**, choose `e2e\fixtures\valid.png`, then **Calculate SHA-256 & register inventory**. Open the row. Say: “The case API stores metadata and the client-declared hash; it does not preserve the original.”
3. Select **Request analysis**. Say: “Each requested check has its own event and status. There is no combined authenticity verdict.”
4. Select a finding observation or location chip. Say: “The viewer links the exact region or timestamp to the finding's method, scope, and limitations.”
5. Enter a reviewer note and select **Add note**. Say: “The note is append-only and separate; it never edits the machine result.”
6. Show a partial/failed example using committed fixture mode or the guarded E2E demonstration only. Say: “Partial and unexamined are never passes. Completed findings remain visible, while failed checks retain their error.”
7. Select **Retry (new run)**. Say: “Retry creates a child attempt and reruns only failed checks. The parent status, findings, and events remain unchanged.”
8. Open video evidence. Select an unexamined sample, then a finding marker. Say: “This is bounded timestamp sampling. Coverage and gaps are visible; it is not exhaustive video analysis.”
9. Select **Evaluation**. Show unavailable, invalid, or loaded publication honestly. Say: “Unavailable is not zero; invalid never renders partial metrics; loaded results retain dataset and limitation context.”
10. Select a run/finding, reload the browser, and show restoration. Say: “The URL and server records restore the valid selection; a stale run ID degrades to the latest valid run.”

## Repeatable seed/reset

The seed command above deletes only the explicitly selected demo database and refuses `backend/data/pratyaksh.db`. It creates fixed IDs, timestamp, hash, and metadata. Verification command:

```powershell
$first = .\backend\.venv\Scripts\python.exe backend\scripts\seed_d4_demo.py --database backend\data\d4-demo.db
$second = .\backend\.venv\Scripts\python.exe backend\scripts\seed_d4_demo.py --database backend\data\d4-demo.db
if ($first -ne $second) { throw 'D4 seed is not repeatable' }
```

Expected: no output after the two identical JSON lines are assigned.

## Fallback procedures

| Failure | Action |
| --- | --- |
| Backend will not start | Show `docs/d4/screenshots/`; then use fixture mode below. Keep the error visible if discussing it. |
| Run hangs | Open run details, note queued/running state, restart only after preserving the error context; do not call it completed. |
| Video is slow/fails | Use `e2e/fixtures/valid.mp4` in the guarded E2E demo or committed video fixture; explain sampled coverage. |
| Evaluation unavailable | State that no publication is available; use the screenshot and never substitute zero metrics. |
| Network/clipboard fails | Use loopback URLs and type the short commands/IDs; do not depend on clipboard. |
| Browser crashes | Restart Chromium and reopen the hash URL; show restoration. If unavailable, use screenshots. |

Fully offline fixture fallback:

```powershell
cd C:\Users\HP\Pratyaksh
Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:VITE_D1_API_BASE_URL -ErrorAction SilentlyContinue
$env:VITE_DEV_FIXTURE = 'true'
npm run dev
```

Expected: the UI labels fixture mode and loads illustrative records. No HTTP analysis occurs. Pre-captured views are in `docs/d4/screenshots/`. Regenerate them with `npm run test:e2e:demo`.

## Likely questions

- **How accurate is it?** No product accuracy claim is supported. Published evaluation must name dataset, split, model version, threshold, coverage, failures, and limitations.
- **What does inconclusive mean?** The check executed, but no validated decision threshold supports pass/fail. It is not “probably authentic.”
- **Why is coverage partial?** Video analysis selects bounded timestamps (at most 12 frames) to control runtime. Unsampled content remains unexamined.
- **Does SHA-256 prove authenticity?** No. It can show whether bytes match a recorded reference, not whether depicted events are genuine.
- **Is this chain of custody?** No. Current SQLite events are ordinary operational records, not tamper-evident storage.
- **Who is the analyst?** The name is self-declared. There is no authentication or authorization.

## Post-demo cleanup

1. Stop both servers with `Ctrl+C`.
2. Clear test variables: `Remove-Item Env:PRATYAKSH_ENV,Env:PRATYAKSH_E2E_STUB -ErrorAction SilentlyContinue`.
3. Keep `backend\data\d4-demo.db` only if another demo needs it; the reset command can recreate it exactly.
4. Do not delete or replace `backend\data\pratyaksh.db` as part of demo cleanup.
