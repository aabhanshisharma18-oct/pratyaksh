"""Exercise the real FastAPI routes in process, without a listening socket."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi import FastAPI
from cases.repository import CaseRepository
from reports.router import create_reports_router


class ReportApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cases = CaseRepository(Path(self.tmp.name) / "cases.db")
        self.case = self.cases.create_case("Report API test", "Integration test", "Bhumi")
        self.app = FastAPI()
        self.app.include_router(create_reports_router(self.cases))

    async def request(self, method, path, payload=None, query=""):
        messages = []
        body = json.dumps(payload).encode() if payload is not None else b""
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(message):
            messages.append(message)
        await self.app({"type": "http", "asgi": {"version": "3.0"},
                        "http_version": "1.1", "method": method, "scheme": "http",
                        "path": path, "raw_path": path.encode(), "query_string": query.encode(),
                        "headers": [(b"content-type", b"application/json")],
                        "server": ("test", 80), "client": ("test", 1), "root_path": ""}, receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        raw = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        return start["status"], dict(start["headers"]), raw

    async def test_save_reopen_export_and_revision_history(self):
        case_id = self.case["id"]
        status, _, raw = await self.request("POST", f"/api/cases/{case_id}/reports", {"preparer": "Bhumi"})
        self.assertEqual(status, 201)
        saved = json.loads(raw)
        report_id = saved["snapshot"]["report_id"]
        status, _, raw = await self.request("GET", f"/api/reports/{report_id}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), saved)
        status, headers, json_bytes = await self.request("GET", f"/api/reports/{report_id}/export", query="format=json")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"x-report-sha256"].decode(), saved["sha256"])
        status, _, raw = await self.request("GET", f"/api/reports/{report_id}/export", query="format=zip")
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            self.assertEqual(bundle.read("report.json"), json_bytes)
        await self.request("POST", f"/api/cases/{case_id}/reports", {"preparer": "Bhumi"})
        status, _, raw = await self.request("GET", f"/api/cases/{case_id}/reports")
        self.assertEqual(status, 200)
        self.assertEqual([item["revision"] for item in json.loads(raw)["items"]], [2, 1])

    async def test_invalid_requests(self):
        for method, path, payload, expected in [
            ("POST", "/api/cases/missing/reports", {"preparer": "Bhumi"}, 404),
            ("GET", "/api/reports/missing", None, 404),
            ("POST", f'/api/cases/{self.case["id"]}/reports', {"preparer": " "}, 422),
            ("POST", f'/api/cases/{self.case["id"]}/reports', {"preparer": "Bhumi", "findings": []}, 422),
        ]:
            status, _, _ = await self.request(method, path, payload)
            self.assertEqual(status, expected)

    async def test_run_options_and_invalid_selection(self):
        path = f'/api/cases/{self.case["id"]}/reports'
        status, _, raw = await self.request("GET", path + "/run-options")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), {"items": []})
        for run_ids in ([], ["other-case-run"]):
            status, _, _ = await self.request("POST", path, {"preparer": "Bhumi", "run_ids": run_ids})
            self.assertEqual(status, 422)
        status, _, _ = await self.request("GET", "/api/cases/missing/reports/run-options")
        self.assertEqual(status, 404)

    async def test_sections_are_saved_and_required_content_cannot_be_hidden(self):
        path = f'/api/cases/{self.case["id"]}/reports'
        sections = ["methods", "findings", "coverage", "limitations"]
        status, _, raw = await self.request("POST", path, {"preparer": "Bhumi", "sections": sections})
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(raw)["snapshot"]["sections"], sections)
        for invalid in ([], ["evidence", "notes"], sections + ["unknown"]):
            status, _, _ = await self.request("POST", path, {"preparer": "Bhumi", "sections": invalid})
            self.assertEqual(status, 422)

    async def test_review_endpoint_creates_linked_revision_and_rejects_bad_input(self):
        _, _, raw = await self.request("POST", f'/api/cases/{self.case["id"]}/reports', {"preparer": "Bhumi"})
        source = json.loads(raw)
        path = f'/api/reports/{source["snapshot"]["report_id"]}/reviews'
        payload = {"reviewer": "Bhumi", "status": "questioned", "note": "Need source confirmation"}
        status, _, raw = await self.request("POST", path, payload)
        self.assertEqual(status, 201)
        reviewed = json.loads(raw)
        self.assertEqual(reviewed["snapshot"]["review_status"], "questioned")
        self.assertEqual(reviewed["snapshot"]["parent_report_sha256"], source["sha256"])
        for bad in ({**payload, "status": "approved"}, {**payload, "reviewer": " "},
                    {**payload, "note": " "}, {**payload, "findings": []}):
            status, _, _ = await self.request("POST", path, bad)
            self.assertEqual(status, 422)
        status, _, _ = await self.request("POST", "/api/reports/missing/reviews", payload)
        self.assertEqual(status, 404)

    async def test_analyst_context_and_audit_export(self):
        status, _, raw = await self.request("POST", f'/api/cases/{self.case["id"]}/reports',
            {"preparer": "Bhumi", "questions": "What scope was examined?", "next_steps": "Ask for original media"})
        self.assertEqual(status, 201)
        source = json.loads(raw)
        self.assertEqual(source["snapshot"]["analyst_context"]["next_steps"], "Ask for original media")
        self.assertEqual(source["snapshot"]["audit_summary"]["included_count"], 1)
        status, _, raw = await self.request("GET", f'/api/reports/{source["snapshot"]["report_id"]}/export')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), source["snapshot"])

    async def test_opt_in_artifact_package_and_corrupt_export_response(self):
        import hashlib
        import sqlite3
        from types import SimpleNamespace
        evidence = self.cases.register_evidence(self.case["id"], {"filename": "test.png", "media_type": "image",
            "role": "Evidence", "size_bytes": 4, "sha256": "a" * 64}, "Bhumi")
        self.cases.register_finding({"finding_id": "F-export", "run_id": "RUN-export", "evidence_id": evidence["evidence_id"],
            "category": "tampering", "execution_status": "completed", "fixture": True, "support_refs": ["ART-export"]}, self.case["id"])
        artifact = b"test verified artifact"
        reader = SimpleNamespace(read=lambda case_id, reference: (artifact, {"sha256": hashlib.sha256(artifact).hexdigest()}))
        self.app = FastAPI()
        self.app.include_router(create_reports_router(self.cases, artifact_reader=reader))
        status, _, raw = await self.request("POST", f'/api/cases/{self.case["id"]}/reports', {"preparer": "Bhumi", "include_artifacts": True})
        self.assertEqual(status, 201)
        saved = json.loads(raw)
        self.assertEqual(saved["snapshot"]["package_policy"]["verified_artifact_count"], 1)
        path = f'/api/reports/{saved["snapshot"]["report_id"]}/export'
        status, _, raw = await self.request("GET", path, query="format=zip")
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            self.assertTrue(manifest["artifact_bytes_included"])
        with sqlite3.connect(self.cases.database_path) as db:
            db.execute("UPDATE report_artifact_blobs SET content=?", (b"corrupt",))
        status, _, _ = await self.request("GET", path, query="format=zip")
        self.assertEqual(status, 409)
