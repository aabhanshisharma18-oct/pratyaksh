"""Publish existing authentication and provenance outputs as case findings."""
import asyncio
import hashlib
import io
import json
import uuid

from fastapi import UploadFile
from importlib import import_module

d2 = import_module("d2.api.router")
from provenance import CaseComparison, analyze_case_originals


def register(cases, job, evidence_id, category, method, observation, *, result="inconclusive",
             details=None, limitations=None, refs=None, failed=False):
    finding = {
        "schema_version": "1.1", "finding_id": "F-" + uuid.uuid4().hex,
        "run_id": job["id"] + "-" + category, "evidence_id": evidence_id,
        "category": category, "execution_status": "failed" if failed else "completed",
        "result": None if failed else result, "observation": observation,
        "method": method, "method_version": "1.0", "scope": "Preserved case evidence",
        "score": None, "location": None, "support_refs": refs or [],
        "limitations": limitations or [], "details": details,
        "review_status": "unreviewed", "fixture": False,
    }
    cases.register_finding(finding, job["case_id"])


def authenticate(cases, job, item, evidence, content):
    services = d2.services
    matches = [record for record in services.intake.list(job["case_id"])
               if record.sha256 == evidence["sha256"]]
    if matches:
        original = matches[0]
    else:
        upload = UploadFile(io.BytesIO(content), filename=evidence["filename"])
        try:
            original = asyncio.run(services.intake.intake(
                job["case_id"], upload, "Automated ZIP intake " + job["id"], job["actor"]))
        finally:
            upload.file.close()
    item["authentication_evidence_id"] = original.id
    verified = services.integrity.verify(original.id, job["actor"])
    expected = evidence["sha256"]
    intact = verified["actual_sha256"] == expected == verified["expected_sha256"]
    register(cases, job, item["evidence_id"], "integrity", "SHA-256 verification",
        "Preserved bytes match the ZIP intake fingerprint." if intact else "Stored bytes differ from the intake fingerprint.",
        result="no_indicators_detected" if intact else "indicators_detected", details=verified,
        limitations=["Byte integrity is measured against intake; earlier content edits require separate examination."])
    if not intact:
        raise ValueError("Original fingerprint verification failed.")
    metadata = services.metadata.extract(original.id, job["actor"])
    normalized = json.loads(json.dumps(metadata.normalized, default=str))
    register(cases, job, item["evidence_id"], "provenance", "Recorded file metadata",
        "Extracted information recorded in the submitted file.", details=normalized,
        limitations=["Metadata can be edited or stripped. Recorded camera or software tags are source clues."])
    if item["media_type"] == "audio":
        register(cases, job, item["evidence_id"], "tampering", "Audio inspection scope",
            "Audio decode and anti-spoofing are examined by the audio run; splice localization is unavailable.",
            limitations=["No audio splice localization method is implemented."])
        return {"evidence_id": original.id, "metadata": "extracted", "tampering": "audio_scope_recorded"}
    if item["media_type"] == "image":
        result = d2.copy_move(original.id, None, 16, 8, 3, job["actor"])
    else:
        result = d2.video_continuity(original.id, 1.0, 120, 120, None, job["actor"])
    completed = result["analysis"] in {"Completed", "Partial"}
    regions = result["findings"].get("possible_regions", [])
    register(cases, job, item["evidence_id"], "tampering", result["algorithm"], result["interpretation"],
        result="indicators_detected" if regions else "inconclusive",
        details={"configuration": result["parameters"], "d2_evidence_id": original.id,
                 "analysis": result["findings"], "artifacts": result["artifacts"]},
        refs=[record["download_url"] for record in result["artifacts"]],
        limitations=result["limitations"], failed=not completed)
    if not completed:
        raise ValueError(result["interpretation"])
    return {"evidence_id": original.id, "run_id": result["run_id"]}


def relate(cases, job, items):
    report = analyze_case_originals(job["case_id"], CaseComparison(
        evidence_ids=[item["evidence_id"] for item in items]))
    for image in report["images"]:
        related = [edge for edge in report["relationships"]
                   if image["id"] in (edge["left_id"], edge["right_id"])]
        exact = [edge for edge in related if edge["kind"] == "exact_copy"]
        register(cases, job, image["case_evidence_id"], "provenance", "Case media relationship analysis",
            f"Found {len(exact)} exact-copy links and {len(related)-len(exact)} other supported relationships.",
            details={"analysis_id": report["analysis_id"], "relationships": related,
                     "content_credentials": image.get("content_credentials"),
                     "methods": report["methods"]},
            limitations=report["limitations"],
            refs=["/api/d1/provenance/reports/" + report["analysis_id"]])
    return {"analysis_id": report["analysis_id"], "relationships": len(report["relationships"])}
