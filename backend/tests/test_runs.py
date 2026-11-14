import hashlib
import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cases.repository import CaseRepository
from runs.repository import RunRepository, aggregate_run_status
from runs.router import create_runs_router


class CapturingScheduler:
    def __init__(self):
        self.ids = []

    def enqueue(self, run_id):
        self.ids.append(run_id)


class PersistentRunTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.folder.name)
        self.db = self.root / "runs.db"
        self.cases = CaseRepository(self.db)
        case = self.cases.create_case("Run test", None, "Aadya")
        self.case_id = case["id"]
        self.raw = b"registered bytes"
        self.sha = hashlib.sha256(self.raw).hexdigest()
        self.cases.register_evidence(self.case_id, {
            "filename": "sample.png", "media_type": "image", "role": "Evidence",
            "size_bytes": len(self.raw), "sha256": self.sha,
        }, "Aadya")
        self.runs = RunRepository(self.db)
        self.scheduler = CapturingScheduler()
        app = FastAPI()
        app.include_router(create_runs_router(self.runs, self.scheduler, self.root / "media"), prefix="/api")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.folder.cleanup()

    def test_migration_creates_tables_indexes_and_version(self):
        connection = sqlite3.connect(self.db)
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            version = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        finally:
            connection.close()
        self.assertTrue({"runs", "run_events"}.issubset(tables))
        self.assertTrue({"idx_runs_evidence_created", "idx_run_events_run_seq"}.issubset(indexes))
        self.assertEqual(version, 5)

    def test_create_get_list_round_trip(self):
        response = self.client.post(
            "/api/evidence/EVID-1/runs",
            data={"case_id": self.case_id},
            files={"file": ("sample.png", self.raw, "image/png")},
        )
        self.assertEqual(response.status_code, 202)
        run = response.json()
        self.assertEqual(run["execution_status"], "queued")
        self.assertEqual(self.scheduler.ids, [run["run_id"]])
        fetched = self.client.get(f"/api/runs/{run['run_id']}")
        listed = self.client.get(f"/api/evidence/EVID-1/runs?case_id={self.case_id}")
        self.assertEqual(fetched.json()["run_id"], run["run_id"])
        self.assertEqual(listed.json()["items"][0]["run_id"], run["run_id"])

    def test_retry_links_run_and_carries_completed_findings_by_reference(self):
        input_path = self.root / "sample.png"
        input_path.write_bytes(self.raw)
        parent = self.runs.create_run("EVID-1", self.case_id, input_path=str(input_path))
        for check in parent["requested_checks"]:
            self.runs.append_event(parent["run_id"], check, "check.started", "running")
        finding = {"finding_id": "F-parent", "run_id": parent["run_id"], "evidence_id": "EVID-1"}
        self.runs.append_event(parent["run_id"], "image_model", "check.completed", "completed", {"findings": [finding]})
        self.runs.append_event(parent["run_id"], "face_forgery", "check.failed", "failed", {"error": {"code": "X"}})
        self.runs.append_event(parent["run_id"], "file_inspection", "check.failed", "failed", {"error": {"code": "Y"}})
        retry = self.runs.create_run("EVID-1", self.case_id, parent["run_id"], ["face_forgery"])
        self.assertEqual(retry["retry_of"], parent["run_id"])
        self.assertEqual(retry["attempt"], 2)
        self.assertEqual(retry["requested_checks"], ["face_forgery"])
        self.assertEqual(retry["findings"][0]["finding_id"], "F-parent")
        carried = next(event for event in retry["events"] if event["event_type"] == "carried_forward")
        self.assertEqual(carried["payload"]["carried_from_run_id"], parent["run_id"])

        retry_finding = {
            "finding_id": "F-retry", "run_id": retry["run_id"], "evidence_id": "EVID-1",
        }
        self.runs.append_event(
            retry["run_id"], "face_forgery", "check.completed", "completed",
            {"findings": [retry_finding]},
        )
        for item in (finding, retry_finding):
            note = self.cases.add_finding_note(item["finding_id"], "reviewed", "Reviewed", "Aadya")
            self.assertEqual(self.cases.list_finding_notes(item["finding_id"]), [note])

    def test_backfill_restores_legacy_run_findings(self):
        run = self.runs.create_run("EVID-1", self.case_id)
        finding = {"finding_id": "F-legacy", "run_id": run["run_id"], "evidence_id": "EVID-1"}
        self.runs.append_event(run["run_id"], "image_model", "check.completed", "completed",
                               {"findings": [finding]})
        with sqlite3.connect(self.db) as connection:
            connection.execute("DELETE FROM findings WHERE finding_id = ?", (finding["finding_id"],))
        self.runs.backfill_review_findings()
        self.runs.backfill_review_findings()
        self.assertEqual(self.cases.list_finding_notes(finding["finding_id"]), [])

    def test_completed_event_cannot_be_changed_or_deleted(self):
        run = self.runs.create_run("EVID-1", self.case_id)
        self.runs.append_event(run["run_id"], "image_model", "check.completed", "completed", {"findings": []})
        connection = sqlite3.connect(self.db)
        try:
            event_id = connection.execute(
                "SELECT id FROM run_events WHERE run_id=? AND status='completed'", (run["run_id"],)
            ).fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM run_events WHERE id=?", (event_id,))
        finally:
            connection.close()

    def test_restart_recovery_marks_active_checks_failed(self):
        run = self.runs.create_run("EVID-1", self.case_id)
        self.runs.append_event(run["run_id"], "image_model", "check.started", "running")
        self.assertEqual(self.runs.recover_stale_runs(), 1)
        recovered = self.runs.get_run(run["run_id"])
        self.assertEqual(recovered["execution_status"], "failed")
        self.assertTrue(any(error["code"] == "SERVER_RESTART" for error in recovered["errors"]))


class AggregationTests(unittest.TestCase):
    def test_all_supported_aggregations(self):
        self.assertEqual(aggregate_run_status(["completed", "completed"]), "completed")
        self.assertEqual(aggregate_run_status(["failed", "failed"]), "failed")
        self.assertEqual(aggregate_run_status(["completed", "failed"]), "partial")
        self.assertEqual(aggregate_run_status(["timeout"]), "failed")
        self.assertEqual(aggregate_run_status(["unexamined"]), "partial")
        self.assertEqual(aggregate_run_status(["queued"]), "queued")
        self.assertEqual(aggregate_run_status(["running", "completed"]), "running")


if __name__ == "__main__":
    unittest.main()
