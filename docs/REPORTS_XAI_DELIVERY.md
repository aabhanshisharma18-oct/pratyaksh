# Reports and explainable findings delivery

This batch imports the report snapshot and explainable findings modules from the local Pratyaksh source. The existing backend/reports implementation is retained. No existing target files are replaced.

## Commit order

1. add finding contracts and shared evidence models.
2. add reproducible finding fixtures and loaders.
3. add run context for explainable findings.
4. add finding labels locations and evidence coverage.
5. add explainable finding card view models.
6. add accessible finding detail components.
7. add analyst review notes and API client.
8. add XAI findings panel and technical details.
9. add case report snapshots with provenance context.
10. test and document reports and XAI delivery.

## Delivered behavior

Finding cards separate execution state, analytic result and analyst review. They expose scope, explicit run coverage, locations, raw score meaning, method versions, limitations and supporting artifact availability. Review notes remain separate from machine observations. Technical details can be exported. Report snapshots record case, evidence, findings, notes, revision and available provenance context; local evidence source URLs are excluded. Development fixtures are opt-in and are disabled in API mode.

## Integration limits

This is a module delivery into a partial repository. The application shell, main frontend entry point, dashboard wiring, base styles and other teammates' modules are separate deliveries. These modules do not by themselves make the complete website runnable. The source folder is an older revision than parts of the target repository, so existing target implementations are preserved.

## Validation

All 58 imported files were compared byte-for-byte with the source. Added JSON files parse, and relative imports within imported TypeScript files resolve. Existing finding semantics, model/fixture and run lifecycle tests are included. Runtime tests and a full TypeScript build could not run: dependencies are not installed and offline npm installation failed because yallist was not cached. Run the checks after installing dependencies and completing application integration:

```sh
npm ci
npm test -- frontend/src/findings/findings.test.ts frontend/src/model.test.ts frontend/src/runs/runs.test.ts
npm run build
```
