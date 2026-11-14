import asyncio
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi import FastAPI
from cases.repository import CaseRepository
from runs.repository import RunRepository
from reports.router import create_reports_router
from reports.scenarios import seed_scenario
from reports.store import canonical


class ReportingScenarioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cases = CaseRepository(Path(self.tmp.name) / "cases.db")
        self.runs = RunRepository(self.cases.database_path)
        self.app = FastAPI()
        self.app.include_router(create_reports_router(self.cases, self.runs))

    def request(self, method, path, payload=None, query=""):
        async def call():
            messages = []
            async def receive():
                return {"type": "http.request", "body": json.dumps(payload).encode() if payload else b"", "more_body": False}
            async def send(message):
                messages.append(message)
            await self.app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "method": method, "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": query.encode(),
                "headers": [(b"content-type", b"application/json")], "server": ("test", 80), "client": ("test", 1), "root_path": ""}, receive, send)
            status = next(item["status"] for item in messages if item["type"] == "http.response.start")
            self.assertIn(status, (200, 201), messages)
            return b"".join(item.get("body", b"") for item in messages)
        return asyncio.run(call())

    def verify_scenario(self, name):
        case_id, run_id = seed_scenario(self.cases, self.runs, name)
        body = {"preparer": "Bhumi", "run_ids": [run_id], "questions": "Illustrative reporting contract test"}
        source = json.loads(self.request("POST", f"/api/cases/{case_id}/reports", body))
        snapshot, report_id = source["snapshot"], source["snapshot"]["report_id"]
        records = self.cases.list_findings(case_id)
        self.assertTrue(snapshot["fixture"])
        self.assertEqual(snapshot["findings"], records)
        self.assertEqual(snapshot["run_selection"]["run_ids"], [run_id])
        for record in records:
            self.assertEqual(record["finding_sha256"], hashlib.sha256(canonical(record["finding"])).hexdigest())
        self.assertTrue(any(item["status"] == "not_assessed" for item in snapshot["coverage"]))
        self.assertEqual(snapshot["source_references"]["runs"][0]["status"], "recorded")
        self.assertEqual([item["status"] for item in snapshot["source_references"]["artifacts"]], ["metadata_recorded", "unresolved"])
        self.assertTrue(any(snapshot["review_notes"].values()))
        findings = [record["finding"] for record in records]
        by_category = {item["category"]: item for item in findings}
        if name == "genuine":
            self.assertEqual(by_category["synthetic_media"]["result"], "no_indicators_detected")
            self.assertIn("not a detector verdict", snapshot["case"]["description"])
        elif name == "manipulated":
            self.assertTrue(all(item["result"] == "indicators_detected" for item in findings))
        elif name == "mixed":
            self.assertEqual(by_category["synthetic_media"]["result"], "indicators_detected")
            self.assertEqual(by_category["integrity"]["details"]["comparison"], "match")
            self.assertEqual(by_category["provenance"]["details"]["manifest"], "no")
        elif name == "partial":
            self.assertEqual(self.runs.get_run(run_id)["execution_status"], "partial")
            self.assertEqual(by_category["tampering"]["execution_status"], "failed")
            self.assertIsNone(by_category["tampering"]["result"])
        else:
            self.assertEqual(by_category["synthetic_media"]["result"], "inconclusive")
        reviewed = json.loads(self.request("POST", f"/api/reports/{report_id}/reviews", {
            "reviewer": "Bhumi", "status": "questioned", "note": "Illustrative review; original media required"}))
        self.assertEqual(reviewed["snapshot"]["findings"], records)
        self.assertEqual(reviewed["snapshot"]["parent_report_sha256"], source["sha256"])
        self.assertEqual(json.loads(self.request("GET", f"/api/reports/{report_id}")), source)
        for saved in (source, reviewed):
            saved_id = saved["snapshot"]["report_id"]
            raw = self.request("GET", f"/api/reports/{saved_id}/export", query="format=json")
            self.assertEqual(hashlib.sha256(raw).hexdigest(), saved["sha256"])
            with zipfile.ZipFile(io.BytesIO(self.request("GET", f"/api/reports/{saved_id}/export", query="format=zip"))) as bundle:
                self.assertEqual(bundle.read("report.json"), raw)
                manifest = json.loads(bundle.read("manifest.json"))
                self.assertEqual(manifest["files"][0]["sha256"], saved["sha256"])

    def test_genuine_scenario(self): self.verify_scenario("genuine")
    def test_manipulated_scenario(self): self.verify_scenario("manipulated")
    def test_mixed_scenario(self): self.verify_scenario("mixed")
    def test_partial_scenario(self): self.verify_scenario("partial")
    def test_inconclusive_scenario(self): self.verify_scenario("inconclusive")
