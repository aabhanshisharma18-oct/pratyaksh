import json
import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cases.repository import CaseRepository
from cases.router import create_cases_router


class ReviewNoteApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.database_path = Path(self.folder.name) / "review.db"
        self.repository = CaseRepository(self.database_path)
        app = FastAPI()
        app.include_router(create_cases_router(self.repository), prefix="/api")
        self.client = TestClient(app)
        case = self.client.post("/api/cases", json={"title": "Review case"}).json()
        self.case_id = case["id"]
        self.client.post(
            f"/api/cases/{self.case_id}/evidence",
            json={"evidence_id": "EVID-1", "filename": "sample.png", "media_type": "image", "role": "Evidence", "size_bytes": 12, "sha256": "a" * 64},
        )
        self.finding = {
            "finding_id": "F-abc123", "evidence_id": "EVID-1", "run_id": "RUN-abc123",
            "observation": "Machine observation", "result": "inconclusive",
        }
        response = self.client.post("/api/findings", json={"case_id": self.case_id, "finding": self.finding})
        self.assertEqual(response.status_code, 201)

    def tearDown(self):
        self.client.close()
        self.folder.cleanup()

    def test_registration_is_idempotent_and_conflicts_are_rejected(self):
        repeated = self.client.post("/api/findings", json={"case_id": self.case_id, "finding": self.finding})
        self.assertEqual(repeated.status_code, 201)
        changed = self.client.post("/api/findings", json={"case_id": self.case_id, "finding": {**self.finding, "observation": "Changed"}})
        self.assertEqual(changed.status_code, 409)

    def test_notes_are_append_only_ordered_and_preserve_finding_snapshot(self):
        before = self.repository.register_finding(self.finding, self.case_id)
        first = self.client.post(
            "/api/findings/F-abc123/notes", json={"status": "reviewed", "text": "Reviewed independently."},
            headers={"X-Analyst-Name": "Aadya"},
        )
        second = self.client.post(
            "/api/findings/F-abc123/notes", json={"status": "questioned", "text": "Needs another check."},
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.json()["note_id"], second.json()["note_id"])
        self.assertEqual(first.json()["author"], "Aadya")
        self.assertFalse(first.json()["author_verified"])
        listing = self.client.get("/api/findings/F-abc123/notes").json()["items"]
        self.assertEqual([item["status"] for item in listing], ["reviewed", "questioned"])
        after = self.repository.register_finding(self.finding, self.case_id)
        self.assertEqual(before["finding_sha256"], after["finding_sha256"])
        self.assertEqual(before["finding"], after["finding"])
        self.assertEqual({item["finding_sha256"] for item in listing}, {before["finding_sha256"]})
        self.assertIn(self.client.patch("/api/findings/F-abc123/notes/anything", json={}).status_code, (404, 405))
        self.assertIn(self.client.delete("/api/findings/F-abc123/notes/anything").status_code, (404, 405))

    def test_note_validation_and_unknown_finding(self):
        invalid = [
            {"status": "accepted", "text": "x"}, {"status": "reviewed", "text": "   "},
            {"status": "reviewed", "text": "x" * 2001}, {"status": "reviewed", "text": "bad\u0000text"},
            {"status": "reviewed", "text": "x", "author": "client"},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/findings/F-abc123/notes", json=payload).status_code, 422)
        self.assertEqual(self.client.post("/api/findings/F-missing/notes", json={"status": "reviewed", "text": "x"}).status_code, 404)
        self.assertEqual(self.client.get("/api/findings/F-missing/notes").status_code, 404)

    def test_notes_survive_repository_restart(self):
        self.client.post("/api/findings/F-abc123/notes", json={"status": "reviewed", "text": "Persistent note"})
        fresh = CaseRepository(self.database_path)
        self.assertEqual(fresh.list_finding_notes("F-abc123")[0]["text"], "Persistent note")
        self.assertEqual(fresh.list_findings(self.case_id)[0]["finding_id"], "F-abc123")


class MigrationTests(unittest.TestCase):
    def test_v1_database_upgrades_without_losing_cases(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            path = Path(folder) / "v1.db"
            connection = sqlite3.connect(path)
            connection.executescript("""
                CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                INSERT INTO schema_version VALUES(1, '2026-01-01T00:00:00.000Z');
                CREATE TABLE cases(id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL);
                INSERT INTO cases VALUES('CASE-2026-000001','Existing','Kept','Open','2026-01-01T00:00:00.000Z','Demo analyst');
            """)
            connection.commit()
            connection.close()
            repository = CaseRepository(path)
            self.assertTrue(repository.ready())
            self.assertEqual(repository.get_case("CASE-2026-000001")["title"], "Existing")
            upgraded = sqlite3.connect(path)
            self.assertEqual(upgraded.execute("SELECT MAX(version) FROM schema_version").fetchone()[0], 5)
            self.assertIn("receipt_json", {row[1] for row in upgraded.execute("PRAGMA table_info(case_evidence)")})
            tables = {row[0] for row in upgraded.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            upgraded.close()
            self.assertTrue({"findings", "finding_notes", "finding_events"}.issubset(tables))


if __name__ == "__main__":
    unittest.main()
