import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from case_briefing import (BriefingError, canonical, collect_snapshot, create_briefing_router,
                           prune_generate, recorded_cautions)
from cases.repository import CaseRepository
from runs.repository import RunRepository


def explanation(snapshot, source_id=None):
    item = {"text": "Review the recorded observation.", "basis": "This check has a recorded method and scope.",
            "source_ids": [source_id or snapshot["sources"][0]["source_id"]]}
    return json.dumps({key: [item] for key in ("key_findings", "open_questions", "next_steps")}), "test-model"


class BriefingTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.repository = CaseRepository(Path(self.folder.name) / "cases.db")
        self.case = self.repository.create_case("Private case title", "Private description", "Analyst")
        self.evidence = self.repository.register_evidence(self.case["id"], {
            "filename": "private-person-name.png", "media_type": "image", "role": "Evidence",
            "size_bytes": 4, "sha256": "a" * 64}, "Private analyst")
        self.finding = {"finding_id": "F-briefing-1", "evidence_id": self.evidence["evidence_id"],
                        "run_id": "RUN-briefing", "category": "synthetic_media", "execution_status": "completed",
                        "result": "inconclusive", "observation": "A synthesis signal was recorded.",
                        "method": "Test detector", "scope": "Whole image", "limitations": ["Not calibrated."],
                        "score": {"value": 0.8, "range": [0, 1], "positive_class": "synthetic",
                                  "interpretation": "Raw model signal", "calibration_status": "not calibrated"},
                        "details": {"metadata": {"GPS": "private location"}, "raw": "PRIVATE_BYTES"},
                        "support_refs": ["https://example.invalid/private"], "fixture": False}
        self.repository.register_finding(self.finding, self.case["id"])

    def tearDown(self):
        self.folder.cleanup()

    def client(self, **options):
        app = FastAPI()
        app.include_router(create_briefing_router(self.repository, **options))
        return TestClient(app)

    @property
    def url(self):
        return f"/api/cases/{self.case['id']}/briefing"

    def test_only_allowlisted_records_leave_the_backend(self):
        sent = []
        def generate(snapshot):
            sent.append(canonical(snapshot))
            return explanation(snapshot)
        with self.client(generate=generate) as client:
            response = client.post(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        for secret in ("private-person", "Private case", "Private description", "Private analyst", "GPS", "PRIVATE_BYTES", "example.invalid"):
            self.assertNotIn(secret, sent[0])
        self.assertIn("Not calibrated", sent[0])
        self.assertIn("inconclusive", response.json()["cautions"][0]["text"])

    def test_citations_are_validated_and_an_unknown_id_is_rejected(self):
        with self.client(generate=lambda snapshot: explanation(snapshot, "S9999")) as client:
            response = client.post(self.url)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("key_findings", response.json())

    def test_malformed_or_uncited_output_is_rejected(self):
        for output in ('not JSON', '{"key_findings": []}', json.dumps({key: [{"text": "Uncited claim", "basis": "None", "source_ids": []}] for key in ("key_findings", "open_questions", "next_steps")})):
            with self.subTest(output=output), self.client(generate=lambda _: (output, "test")) as client:
                self.assertEqual(client.post(self.url).status_code, 502)

    def test_unknown_case_does_not_call_provider(self):
        def forbidden(_):
            self.fail("Provider called for unknown case")
        with self.client(generate=forbidden) as client:
            self.assertEqual(client.post('/api/cases/MISSING/briefing').status_code, 404)

    def test_other_cases_never_enter_prompt(self):
        other = self.repository.create_case("Other", None, "Analyst")
        other_evidence = self.repository.register_evidence(other["id"], {
            "filename": "other.png", "media_type": "image", "role": "Evidence", "size_bytes": 1, "sha256": "b" * 64}, "Analyst")
        self.repository.register_finding({**self.finding, "finding_id": "F-other", "evidence_id": other_evidence["evidence_id"],
                                          "observation": "PRIVATE_OTHER_CASE"}, other["id"])
        snapshot = collect_snapshot(self.repository, self.case["id"])
        self.assertNotIn("PRIVATE_OTHER_CASE", canonical(snapshot))

    def test_exact_snapshot_cache_and_invalidation(self):
        calls = []
        def generate(snapshot):
            calls.append(snapshot)
            return explanation(snapshot)
        with self.client(generate=generate) as client:
            first = client.post(self.url).json()
            second = client.post(self.url).json()
            self.assertFalse(first["cached"])
            self.assertTrue(second["cached"])
            self.repository.register_finding({**self.finding, "finding_id": "F-new"}, self.case["id"])
            third = client.post(self.url).json()
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(first["snapshot_sha256"], third["snapshot_sha256"])

    def test_changed_records_during_generation_are_rejected(self):
        def generate(snapshot):
            self.repository.register_finding({**self.finding, "finding_id": "F-arrived-during-generation"}, self.case["id"])
            return explanation(snapshot)
        with self.client(generate=generate) as client:
            self.assertEqual(client.post(self.url).status_code, 409)

    def test_failed_run_without_a_finding_is_retained(self):
        runs = RunRepository(self.repository.database_path)
        run = runs.create_run(self.evidence["evidence_id"], self.case["id"])
        for check in run["requested_checks"]:
            runs.append_event(run["run_id"], check, "check.failed", "failed", {"error": {"code": "MISSING_MODEL", "message": "Unavailable"}})
        snapshot = collect_snapshot(self.repository, self.case["id"], runs=runs)
        failed = next(source for source in snapshot["sources"] if source["kind"] == "run")
        self.assertEqual(failed["execution_status"], "failed")
        self.assertTrue(recorded_cautions(snapshot["sources"]))

    def test_conflicts_stay_visible_even_when_provider_omits_them(self):
        self.repository.register_finding({**self.finding, "finding_id": "F-positive", "result": "indicators_detected"}, self.case["id"])
        self.repository.register_finding({**self.finding, "finding_id": "F-negative", "result": "no_indicators_detected"}, self.case["id"])
        with self.client(generate=explanation) as client:
            response = client.post(self.url).json()
        self.assertTrue(any("disagree" in notice["text"] for notice in response["cautions"]))

    def test_relationship_cites_exact_saved_report_and_case_evidence_pair(self):
        second = self.repository.register_evidence(self.case["id"], {
            "filename": "crop.png", "media_type": "image", "role": "Evidence", "size_bytes": 2, "sha256": "b" * 64}, "Analyst")
        report = {"case": {"id": self.case["id"]}, "analysis_id": "PROV-snapshot", "limitations": ["Order unknown"],
                  "images": [{"id": "I1", "case_evidence_id": self.evidence["evidence_id"]}, {"id": "I2", "case_evidence_id": second["evidence_id"]}],
                  "relationships": [{"id": "EDGE1", "kind": "matching_content", "left_id": "I1", "right_id": "I2",
                                     "support": {"method": "SIFT", "matched_features": 30, "unapproved": "PRIVATE_METADATA"}}]}
        snapshot = collect_snapshot(self.repository, self.case["id"], provenance=lambda _: report)
        source = next(source for source in snapshot["sources"] if source["kind"] == "relationship")
        self.assertEqual(source["analysis_id"], "PROV-snapshot")
        self.assertEqual(source["relationship_id"], "EDGE1")
        self.assertEqual(source["evidence_ids"], [self.evidence["evidence_id"], second["evidence_id"]])
        self.assertNotIn("PRIVATE_METADATA", canonical(snapshot))

    def test_quota_errors_are_actionable_and_do_not_expose_provider_payload(self):
        with patch.dict(os.environ, {"PRUNE_API_KEY": "prune_TEST_ONLY"}), patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError('url', 429, 'secret upstream body', {}, io.BytesIO(b'PRIVATE_KEY'))):
            with self.client() as client:
                response = client.post(self.url)
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("PRIVATE", response.text)

    def test_native_gemini_response_and_outbound_contract(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{\"ok\":true}"}]}}]}).encode()
        with patch.dict(os.environ, {"PRUNE_API_KEY": "prune_TEST_ONLY"}), patch('urllib.request.urlopen', return_value=response) as send:
            text, _ = prune_generate({"case_id": "CASE-demo", "sources": []})
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.withprune.com/v1/chat/completions')
        self.assertEqual(request.get_header('X-prune-cache'), 'off')
        self.assertEqual(text, '{"ok":true}')
        self.assertNotIn('prune_TEST_ONLY', request.data.decode())

    def test_gateway_errors_redact_credentials_before_display(self):
        failure = json.dumps({"error": {"message": "Failure for prune_TEST_ONLY at https://upstream.invalid/request"}}).encode()
        with patch.dict(os.environ, {"PRUNE_API_KEY": "prune_TEST_ONLY"}), patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError('url', 502, 'failure', {}, io.BytesIO(failure))):
            with self.client() as client:
                response = client.post(self.url)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("prune_TEST_ONLY", response.text)
        self.assertNotIn("upstream.invalid", response.text)
        self.assertIn("Gateway reason", response.text)

    def test_missing_configuration_is_explicit(self):
        with patch.dict(os.environ, {"PRUNE_API_KEY": ""}), self.client() as client:
            response = client.post(self.url)
        self.assertEqual(response.status_code, 503)


if __name__ == '__main__':
    unittest.main()
