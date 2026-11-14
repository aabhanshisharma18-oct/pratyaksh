"""Copy published run context; never follow artifact paths or network URLs."""
from runs.repository import RunNotFoundError

SETTING_KEYS = ("model", "preprocessing_version", "configuration", "configuration_version",
                "threshold", "trust_policy", "weights_sha256", "environment", "sampling")


def run_references(case_id, records, reader=None):
    contexts, artifacts = [], []
    for run_id in sorted({record["run_id"] for record in records}):
        linked = [record for record in records if record["run_id"] == run_id]
        context = {"run_id": run_id, "status": "not_available", "record": None}
        registered = []
        if reader is not None:
            try:
                run = reader.get_run(run_id)
            except RunNotFoundError:
                context["status"] = "not_found"
            else:
                if (run.get("run_id") != run_id or run.get("case_id") != case_id
                        or any(record["evidence_id"] != run.get("evidence_id") for record in linked)):
                    context["status"] = "case_or_evidence_mismatch"
                else:
                    context["status"] = "recorded"
                    context["record"] = {key: run.get(key) for key in (
                        "case_id", "evidence_id", "modality", "execution_status", "requested_at",
                        "started_at", "completed_at", "configuration", "configuration_version",
                        "requested_checks", "coverage", "errors", "retry_of", "attempt")}
                    settings = []
                    registered = list(run.get("artifacts") or [])
                    for event in run.get("events", []):
                        payload = event.get("payload") or {}
                        values = {key: payload[key] for key in SETTING_KEYS if key in payload}
                        if values:
                            settings.append({"event_id": event["id"], "check": event["check"],
                                             "status": event["status"], "settings": values})
                        registered.extend(payload.get("artifacts") or [])
                    context["record"]["check_settings"] = settings
        contexts.append(context)
        for source in linked:
            for reference in dict.fromkeys(source["finding"].get("support_refs", [])):
                matches = [item for item in registered if isinstance(item, dict)
                           and (item.get("artifact_id") or item.get("derivative_id")) == reference
                           and item.get("evidence_id", source["evidence_id"]) == source["evidence_id"]]
                metadata = {key: matches[0][key] for key in ("artifact_id", "derivative_id", "kind", "sha256", "size_bytes")
                            if key in matches[0]} if len(matches) == 1 else None
                artifacts.append({"reference": reference, "finding_id": source["finding_id"],
                                  "run_id": run_id, "evidence_id": source["evidence_id"],
                                  "status": "metadata_recorded" if len(matches) == 1 else "ambiguous" if matches else "unresolved",
                                  "metadata": metadata, "bytes_verified": False, "bytes_included": False})
    return {"runs": contexts, "artifacts": artifacts,
            "limitations": ["Run configuration describes the saved orchestrator record; it is not automatically a model configuration.",
                            "Check settings are copied only when explicitly published in run events.",
                            "Artifact metadata and declared hashes are not verification of artifact bytes.",
                            "Unresolved references have no matching artifact metadata in the published run.",
                            "Artifact inclusion requires an explicit request and case-bound verification; unverified bytes are excluded."]}
