"""Explicitly illustrative D5 contract scenarios. No inference or real evidence."""
import hashlib
import uuid

SCENARIOS = ("genuine", "manipulated", "mixed", "partial", "inconclusive")


def seed_scenario(cases, runs, name):
    if name not in SCENARIOS:
        raise ValueError("Unknown D5 test scenario")
    case = cases.create_case(f"ILLUSTRATIVE D5: {name}",
        "Synthetic reporting test only. Scenario label is not a detector verdict or measured ground truth.", "Bhumi")
    media = "video" if name == "mixed" else "audio" if name == "inconclusive" else "image"
    raw = f"ILLUSTRATIVE PLACEHOLDER {name}".encode()
    evidence = cases.register_evidence(case["id"], {
        "filename": f"illustrative-{name}." + {"image": "png", "video": "mp4", "audio": "wav"}[media],
        "media_type": media, "role": "Evidence", "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, "Bhumi", receipt={"supplied_by": "Illustrative scenario generator", "collection_reference": "D5 contract test",
                         "note": "No original media is supplied or preserved. Hash identifies placeholder test bytes only."})
    run = runs.create_run(evidence["evidence_id"], case["id"])
    def finding(category, result, value=None, status="completed", details=None):
        return {"schema_version": "1.1", "finding_id": "F-" + uuid.uuid4().hex,
            "run_id": run["run_id"], "evidence_id": evidence["evidence_id"], "category": category,
            "execution_status": status, "result": result,
            "observation": "ILLUSTRATIVE: " + ("check failed; no assessment" if status == "failed" else str(result)),
            "method": "Illustrative reporting fixture", "method_version": "demo-only-1.0",
            "scope": "Synthetic contract record; no media examined",
            "score": None if value is None else {"value": value, "range": [0, 1],
                "positive_class": "illustrative_manipulation", "interpretation": "Invented test value, not a probability",
                "calibration_status": "Not calibrated; no inference performed"},
            "location": None, "support_refs": [], "limitations": ["Illustrative reporting fixture only; no detector was run."],
            "review_status": "unreviewed", "error": {"code": "DEMO_FAILURE", "message": "Illustrative failure", "retryable": False} if status == "failed" else None,
            "details": details, "fixture": True}
    if name == "genuine":
        findings = [finding("synthetic_media", "no_indicators_detected", 0.12),
                    finding("integrity", None, details={"kind": "integrity", "comparison": "match"})]
    elif name == "manipulated":
        findings = [finding("synthetic_media", "indicators_detected", 0.87), finding("tampering", "indicators_detected", 0.81)]
    elif name == "mixed":
        findings = [finding("synthetic_media", "indicators_detected", 0.87),
                    finding("integrity", None, details={"kind": "integrity", "comparison": "match"}),
                    finding("provenance", "inconclusive", details={"kind": "provenance", "manifest": "no"})]
    elif name == "partial":
        findings = [finding("synthetic_media", "inconclusive", 0.52), finding("tampering", None, status="failed")]
    else:
        findings = [finding("synthetic_media", "inconclusive", 0.5)]
    findings[0]["support_refs"] = ["ART-DEMO", "ART-UNRESOLVED"]
    checks = run["requested_checks"]
    for index, check in enumerate(checks):
        items = findings if len(checks) == 1 else findings[:1] if index == 0 else findings[1:] if index == 1 else []
        state = "failed" if name == "partial" and index == 1 else "completed"
        payload = {"findings": items, "preprocessing_version": "demo-no-preprocessing", "threshold": None}
        if index == 0:
            payload["artifacts"] = [{"artifact_id": "ART-DEMO", "kind": "illustrative_reference", "sha256": "a" * 64}]
        if state == "failed":
            payload["error"] = {"code": "DEMO_FAILURE", "message": "Illustrative failure", "retryable": False}
        runs.append_event(run["run_id"], check, "check." + state, state, payload)
    cases.add_finding_note(findings[0]["finding_id"], "questioned" if name in ("mixed", "partial", "inconclusive") else "reviewed",
                           "Illustrative analyst note; request source media before any real assessment.", "Bhumi")
    return case["id"], run["run_id"]
