import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from cases.repository import CaseRepository, CaseNotFoundError
from reports.store import ReportStore, canonical


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cases = CaseRepository(Path(self.tmp.name) / "cases.db")
        self.case = self.cases.create_case("Review", "Test investigation", "Bhumi")
        self.store = ReportStore(self.cases)

    def test_section_choice_is_frozen_validated_and_canonical(self):
        sections = ["limitations", "findings", "methods", "coverage"]
        saved = self.store.create(self.case["id"], "Bhumi", sections=sections)
        self.assertEqual(saved["snapshot"]["sections"], ["methods", "findings", "coverage", "limitations"])
        sections.append("notes")
        self.store.create(self.case["id"], "Bhumi")
        self.assertEqual(self.store.get(saved["snapshot"]["report_id"]), saved)
        with zipfile.ZipFile(io.BytesIO(self.store.export(saved["snapshot"]["report_id"]))) as bundle:
            self.assertEqual(json.loads(bundle.read("report.json"))["sections"], saved["snapshot"]["sections"])
        for invalid in ([], ["findings"], ["methods", "findings", "coverage", "limitations", "unknown"],
                        ["methods", "findings", "coverage", "limitations", "methods"]):
            with self.assertRaises(ValueError):
                self.store.create(self.case["id"], "Bhumi", sections=invalid)

    def test_review_preserves_source_and_adds_linked_revisions(self):
        source = self.store.create(self.case["id"], "Bhumi")
        with sqlite3.connect(self.cases.database_path) as db:
            db.execute("UPDATE cases SET title='Changed after save'")
        reviewed = self.store.review(source["snapshot"]["report_id"], "Bhumi", "reviewed", "Checked source references")
        self.assertEqual(self.store.get(source["snapshot"]["report_id"]), source)
        self.assertEqual(reviewed["snapshot"]["revision"], 2)
        self.assertEqual(reviewed["snapshot"]["case"], source["snapshot"]["case"])
        for key in ("findings", "evidence", "review_notes", "coverage", "sections", "run_selection", "preparer", "limitations", "audit_summary", "analyst_context", "source_references"):
            self.assertEqual(reviewed["snapshot"][key], source["snapshot"][key])
        self.assertEqual(reviewed["snapshot"]["parent_report_sha256"], source["sha256"])
        self.assertEqual(reviewed["snapshot"]["prepared_at"], source["snapshot"]["generated_at"])
        questioned = self.store.review(reviewed["snapshot"]["report_id"], "Second reviewer", "questioned", "Need more source material")
        self.assertEqual(questioned["snapshot"]["revision"], 3)
        self.assertEqual(len(questioned["snapshot"]["review_history"]), 2)
        self.assertEqual(questioned["snapshot"]["review_status"], "questioned")
        self.assertEqual(self.store.get(reviewed["snapshot"]["report_id"]), reviewed)
        with zipfile.ZipFile(io.BytesIO(self.store.export(questioned["snapshot"]["report_id"]))) as bundle:
            self.assertEqual(json.loads(bundle.read("report.json")), questioned["snapshot"])

    def test_invalid_reviews_do_not_create_revisions(self):
        source = self.store.create(self.case["id"], "Bhumi")
        for reviewer, status, note in [(" ", "reviewed", "Checked"), ("Bhumi", "approved", "Checked"),
                                       ("Bhumi", "questioned", " "), ("Bad\x00name", "reviewed", "Checked")]:
            with self.assertRaises(ValueError):
                self.store.review(source["snapshot"]["report_id"], reviewer, status, note)
        with self.assertRaises(KeyError):
            self.store.review("missing", "Bhumi", "reviewed", "Checked")
        self.assertEqual(len(self.store.list(self.case["id"])), 1)

    def test_audit_and_analyst_context_are_case_scoped_and_frozen(self):
        self.cases.create_case("Other case", "Must not leak", "Other actor")
        source = self.store.create(self.case["id"], "Bhumi", questions=" What was examined? ", next_steps="Request original source")
        report = source["snapshot"]
        self.assertEqual(report["analyst_context"]["questions"], "What was examined?")
        self.assertEqual(report["audit_summary"]["included_count"], 1)
        self.assertEqual(report["audit_summary"]["counts_by_type"], {"case.created": 1})
        self.assertEqual(report["audit_summary"]["events"][0]["actor"], "Bhumi")
        self.assertNotIn("payload", report["audit_summary"]["events"][0])
        self.cases.register_evidence(self.case["id"], {"filename": "later.jpg", "media_type": "image", "role": "Evidence", "size_bytes": 4, "sha256": "c" * 64}, "Bhumi")
        fresh = self.store.create(self.case["id"], "Bhumi")["snapshot"]
        self.assertEqual(fresh["audit_summary"]["included_count"], 2)
        self.assertEqual(self.store.get(report["report_id"]), source)
        for invalid in ("x" * 2001, "bad\x00text"):
            with self.assertRaises(ValueError):
                self.store.create(self.case["id"], "Bhumi", questions=invalid)

    def test_audit_truncation_is_explicit(self):
        from unittest.mock import patch
        with patch.object(self.cases, "query_events", return_value=([], "older-events-remain")):
            report = self.store.create(self.case["id"], "Bhumi")["snapshot"]
        self.assertTrue(report["audit_summary"]["truncated"])
        self.assertEqual(report["audit_summary"]["included_count"], 0)

    def test_published_run_context_and_artifact_references_are_frozen(self):
        from runs.repository import RunRepository
        self.cases.register_evidence(self.case["id"], {"filename": "test.jpg", "media_type": "image", "role": "Evidence", "size_bytes": 4, "sha256": "d" * 64}, "Bhumi")
        evidence_id = self.cases.list_evidence(self.case["id"])[0]["evidence_id"]
        runs = RunRepository(self.cases.database_path)
        run = runs.create_run(evidence_id, self.case["id"])
        finding = {"finding_id": "F-context", "run_id": run["run_id"], "evidence_id": evidence_id,
                   "category": "synthetic_media", "execution_status": "completed", "fixture": True,
                   "support_refs": ["ART-1", "ART-missing"]}
        runs.append_event(run["run_id"], "image_model", "check.completed", "completed", {
            "findings": [finding], "threshold": 0, "preprocessing_version": "test-v1",
            "artifacts": [{"artifact_id": "ART-1", "kind": "frame", "sha256": "e" * 64, "path": "/private/do-not-read"}]})
        store = ReportStore(self.cases, run_reader=runs)
        saved = store.create(self.case["id"], "Bhumi")
        refs = saved["snapshot"]["source_references"]
        self.assertEqual(refs["runs"][0]["status"], "recorded")
        self.assertEqual(refs["runs"][0]["record"]["check_settings"][0]["settings"]["threshold"], 0)
        self.assertEqual([item["status"] for item in refs["artifacts"]], ["metadata_recorded", "unresolved"])
        self.assertNotIn("path", refs["artifacts"][0]["metadata"])
        self.assertFalse(refs["artifacts"][0]["bytes_verified"])
        runs.append_event(run["run_id"], "file_inspection", "check.completed", "completed", {"threshold": 0.8})
        self.assertEqual(store.get(saved["snapshot"]["report_id"]), saved)

    def test_run_context_from_another_case_is_not_copied(self):
        from reports.references import run_references
        from unittest.mock import Mock
        records = [{"run_id": "RUN-test", "finding_id": "F-test", "evidence_id": "E-test", "finding": {"support_refs": ["ART-1"]}}]
        reader = Mock()
        reader.get_run.return_value = {"run_id": "RUN-test", "case_id": "OTHER", "evidence_id": "E-test", "artifacts": [{"artifact_id": "ART-1"}]}
        refs = run_references(self.case["id"], records, reader)
        self.assertEqual(refs["runs"][0]["status"], "case_or_evidence_mismatch")
        self.assertIsNone(refs["runs"][0]["record"])
        self.assertEqual(refs["artifacts"][0]["status"], "unresolved")

    def test_saved_revision_survives_source_changes_and_restart(self):
        first = self.store.create(self.case["id"], "Bhumi")
        with sqlite3.connect(self.cases.database_path) as db:
            db.execute("UPDATE cases SET title='Changed' WHERE id=?", (self.case["id"],))
        reopened = ReportStore(self.cases).get(first["snapshot"]["report_id"])
        self.assertEqual(first, reopened)
        self.assertEqual(reopened["snapshot"]["case"]["title"], "Review")
        second = self.store.create(self.case["id"], "Bhumi")
        self.assertEqual(second["snapshot"]["revision"], 2)
        self.assertNotEqual(first["snapshot"]["report_id"], second["snapshot"]["report_id"])

    def test_export_manifest_matches_exact_json_bytes(self):
        saved = self.store.create(self.case["id"], "Bhumi")
        with zipfile.ZipFile(io.BytesIO(self.store.export(saved["snapshot"]["report_id"]))) as bundle:
            raw = bundle.read("report.json")
            manifest = json.loads(bundle.read("manifest.json"))
            self.assertEqual(raw, canonical(saved["snapshot"]))
            self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(manifest["files"][0]["size_bytes"], len(raw))
            self.assertFalse(manifest["original_media_included"])

    def test_missing_checks_are_explicit(self):
        self.cases.register_evidence(self.case["id"], {
            "filename": "image.jpg", "media_type": "image", "role": "Evidence",
            "size_bytes": 4, "sha256": "a" * 64,
        }, "Bhumi")
        report = self.store.create(self.case["id"], "Bhumi")["snapshot"]
        self.assertEqual(len(report["coverage"]), 4)
        self.assertTrue(all(item["status"] == "not_assessed" for item in report["coverage"]))
        self.assertEqual(report["findings"], [])

    def test_invalid_requests_and_corruption(self):
        with self.assertRaises(CaseNotFoundError):
            self.store.create("missing", "Bhumi")
        with self.assertRaises(ValueError):
            self.store.create(self.case["id"], " ")
        with self.assertRaises(KeyError):
            self.store.get("missing")
        record = self.store.create(self.case["id"], "Bhumi")
        with sqlite3.connect(self.cases.database_path) as db:
            db.execute("UPDATE report_revisions SET snapshot=?", (b"{}",))
        with self.assertRaises(ValueError):
            self.store.get(record["snapshot"]["report_id"])

    def test_failed_and_inconclusive_findings_keep_source_values(self):
        evidence = self.cases.register_evidence(self.case["id"], {
            "filename": "image.jpg", "media_type": "image", "role": "Evidence",
            "size_bytes": 4, "sha256": "b" * 64,
        }, "Bhumi")
        for index, execution in enumerate(("failed", "completed")):
            finding = {"finding_id": f"F-{index}", "run_id": f"RUN-{index}",
                       "evidence_id": evidence["evidence_id"], "category": "synthetic_media",
                       "execution_status": execution, "result": None if execution == "failed" else "inconclusive",
                       "method": "Test method", "method_version": "test-1", "fixture": True,
                       "observation": "Test observation", "limitations": ["Unevaluated test method"]}
            self.cases.register_finding(finding, self.case["id"])
        records = self.cases.list_findings(self.case["id"])
        report = self.store.create(self.case["id"], "Bhumi")["snapshot"]
        self.assertEqual(report["findings"], records)
        self.assertTrue(report["fixture"])
        self.assertEqual(report["coverage"][0]["finding_ids"], ["F-0", "F-1"])
        selected = self.store.create(self.case["id"], "Bhumi", ["RUN-1"])["snapshot"]
        self.assertEqual([item["finding_id"] for item in selected["findings"]], ["F-1"])
        self.assertEqual(selected["run_selection"], {"mode": "selected", "run_ids": ["RUN-1"], "excluded_finding_count": 1})
        self.assertEqual(selected["coverage"][0]["finding_ids"], ["F-1"])
        self.assertEqual(list(selected["review_notes"]), ["F-1"])
        options = self.store.run_options(self.case["id"])
        self.assertTrue(all(item["selectable"] for item in options))
        self.assertEqual([item["status"] for item in options], ["failed", "completed"])
        for invalid in ([], ["RUN-1", "RUN-1"], ["missing"]):
            with self.assertRaises(ValueError):
                self.store.create(self.case["id"], "Bhumi", invalid)
        with sqlite3.connect(self.cases.database_path) as db:
            db.execute("CREATE TABLE runs (id TEXT, case_id TEXT, status TEXT)")
            db.execute("INSERT INTO runs VALUES (?, ?, ?)", ("RUN-1", self.case["id"], "running"))
        self.assertFalse(next(item for item in self.store.run_options(self.case["id"]) if item["run_id"] == "RUN-1")["selectable"])
        with self.assertRaises(ValueError):
            self.store.create(self.case["id"], "Bhumi", ["RUN-1"])
        # Previously saved selected revisions do not depend on the current run state.
        self.assertEqual(self.store.get(selected["report_id"])["snapshot"], selected)
