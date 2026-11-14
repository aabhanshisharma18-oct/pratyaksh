import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cases.repository import CaseRepository
from cases.router import create_cases_router
from runs.repository import RunRepository


SHA = "a" * 64


class CaseActivityTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.path = Path(self.folder.name) / "activity.db"
        self.repository = CaseRepository(self.path)
        app = FastAPI()
        app.include_router(create_cases_router(self.repository), prefix="/api")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.folder.cleanup()

    def create_case(self, at="2026-01-01T00:00:00.000Z", title="Case"):
        with patch("cases.repository.utc_now", return_value=at):
            return self.repository.create_case(title, None, "Aadya")

    def add_evidence(self, case_id, at="2026-01-02T00:00:00.000Z", evidence_id=None):
        payload = {"filename": "x.png", "media_type": "image", "role": "Evidence",
                   "size_bytes": 1, "sha256": SHA}
        if evidence_id:
            payload["evidence_id"] = evidence_id
        with patch("cases.repository.utc_now", return_value=at):
            return self.repository.register_evidence(case_id, payload, "Aadya")

    def test_last_activity_initializes_and_all_writes_advance_monotonically(self):
        case = self.create_case()
        self.assertEqual(case["last_activity_at"], case["created_at"])
        evidence = self.add_evidence(case["id"])
        self.assertEqual(self.repository.get_case(case["id"])["last_activity_at"], "2026-01-02T00:00:00.000Z")
        finding = {"finding_id": "F-1", "evidence_id": evidence["evidence_id"], "run_id": "RUN-external",
                   "category": "tampering"}
        with patch("cases.repository.utc_now", return_value="2026-01-03T00:00:00.000Z"):
            self.repository.register_finding(finding, case["id"])
        with patch("cases.repository.utc_now", return_value="2026-01-04T00:00:00.000Z"):
            self.repository.add_finding_note("F-1", "reviewed", "Short private note body", "Reviewer")
        self.assertEqual(self.repository.get_case(case["id"])["last_activity_at"], "2026-01-04T00:00:00.000Z")
        with self.repository._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.repository._insert_event(connection, case["id"], "finding.created", "Aadya",
                                          "2025-01-01T00:00:00.000Z", {"finding_id": "old"})
            connection.commit()
        self.assertEqual(self.repository.get_case(case["id"])["last_activity_at"], "2026-01-04T00:00:00.000Z")

    def test_run_events_advance_case_activity(self):
        case = self.create_case()
        evidence = self.add_evidence(case["id"])
        runs = RunRepository(self.path)
        run = runs.create_run(evidence["evidence_id"], case["id"])
        with patch("runs.repository.utc_now", return_value="2026-01-05T00:00:00.000Z"):
            for check in run["requested_checks"]:
                runs.append_event(run["run_id"], check, "check.started", "running")
        with patch("runs.repository.utc_now", return_value="2026-01-06T00:00:00.000Z"):
            for check in run["requested_checks"]:
                runs.append_event(run["run_id"], check, "check.completed", "completed", {"findings": []})
        record = self.repository.get_case(case["id"])
        self.assertEqual(record["last_activity_at"], "2026-01-06T00:00:00.000Z")
        types = [event["event_type"] for event in self.repository.list_events(case["id"])]
        self.assertIn("run.started", types)
        self.assertIn("run.completed", types)

    def test_list_sorting_and_evidence_count(self):
        first = self.create_case(title="First")
        second = self.create_case(title="Second")
        self.add_evidence(first["id"], "2026-01-03T00:00:00.000Z")
        descending, _ = self.repository.list_cases(None, None, 10, 0, "last_activity_at", "desc")
        ascending, _ = self.repository.list_cases(None, None, 10, 0, "last_activity_at", "asc")
        self.assertEqual(descending[0]["id"], first["id"])
        self.assertEqual(ascending[-1]["id"], first["id"])
        self.assertEqual(descending[0]["evidence_count"], 1)
        tied = [item["id"] for item in ascending if item["last_activity_at"] == second["last_activity_at"]]
        self.assertEqual(tied, sorted(tied))

    def test_backfill_is_idempotent(self):
        case = self.create_case()
        self.add_evidence(case["id"])
        with self.repository._connect() as connection:
            before = connection.execute("SELECT COUNT(*) FROM case_events").fetchone()[0]
            self.repository._backfill_events(connection)
            self.repository._backfill_events(connection)
            after = connection.execute("SELECT COUNT(*) FROM case_events").fetchone()[0]
        self.assertGreaterEqual(after, before)
        with self.repository._connect() as connection:
            self.repository._backfill_events(connection)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM case_events").fetchone()[0], after)

    def test_api_filters_pagination_cursor_and_privacy(self):
        case = self.create_case()
        other = self.create_case(title="Other")
        evidence = self.add_evidence(case["id"])
        self.add_evidence(other["id"], evidence_id="OTHER")
        finding = {"finding_id": "F-1", "evidence_id": evidence["evidence_id"], "run_id": "RUN-1",
                   "category": "tampering"}
        self.repository.register_finding(finding, case["id"])
        private_note = "Sensitive beginning " + "private detail " * 20 + "DO-NOT-RETURN-THIS-TAIL"
        self.repository.add_finding_note("F-1", "questioned", private_note, "Reviewer")

        first = self.client.get(f"/api/cases/{case['id']}/events", params={"limit": 2})
        self.assertEqual(first.status_code, 200)
        first_body = first.json()
        second = self.client.get(f"/api/cases/{case['id']}/events", params={"limit": 2, "cursor": first_body["next_cursor"]})
        ids = [item["id"] for item in first_body["items"] + second.json()["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(item["case_id"] == case["id"] for item in first_body["items"] + second.json()["items"]))
        filtered = self.client.get(f"/api/cases/{case['id']}/events", params={"type": "note.added", "actor": "Reviewer", "run_id": "RUN-1"})
        self.assertEqual([item["type"] for item in filtered.json()["items"]], ["note.added"])
        self.assertNotIn("DO-NOT-RETURN-THIS-TAIL", str(filtered.json()))
        self.assertEqual(self.client.get("/api/cases/CASE-2099-999999/events").status_code, 404)
        self.assertEqual(self.client.get(f"/api/cases/{case['id']}/events?type=unknown").status_code, 400)
        self.assertEqual(self.client.get(f"/api/cases/{case['id']}/events?cursor=bad").status_code, 400)

    def test_new_events_between_pages_do_not_duplicate_old_page(self):
        case = self.create_case()
        self.add_evidence(case["id"], "2026-01-02T00:00:00.000Z")
        first = self.client.get(f"/api/cases/{case['id']}/events?limit=1").json()
        self.add_evidence(case["id"], "2026-01-03T00:00:00.000Z", "EVID-new")
        second = self.client.get(f"/api/cases/{case['id']}/events", params={"limit": 10, "cursor": first["next_cursor"]}).json()
        self.assertNotIn(first["items"][0]["id"], [item["id"] for item in second["items"]])


if __name__ == "__main__":
    unittest.main()
