import re
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cases.repository import CaseRepository
from cases.router import create_cases_router


SHA_A = "a" * 64
SHA_B = "b" * 64


class CaseApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.database_path = Path(self.folder.name) / "cases.db"
        self.repository = CaseRepository(self.database_path)
        app = FastAPI()
        app.include_router(create_cases_router(self.repository), prefix="/api")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.folder.cleanup()

    def create_case(self, title="Case one", headers=None):
        return self.client.post(
            "/api/cases",
            json={"title": title, "description": "Context"},
            headers=headers or {},
        )

    def test_create_case_uses_server_identity_and_utc_time(self):
        response = self.create_case()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertRegex(body["id"], r"^CASE-\d{4}-\d{6}$")
        self.assertRegex(body["created_at"], r"(?:Z|\+00:00)$")
        self.assertEqual(body["status"], "Open")
        self.assertEqual(body["created_by"], "Demo analyst")
        self.assertFalse(body["created_by_verified"])

    def test_creator_header_is_self_declared(self):
        response = self.create_case(headers={"X-Analyst-Name": "Aadya"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["created_by"], "Aadya")
        self.assertFalse(response.json()["created_by_verified"])

    def test_case_validation(self):
        invalid_payloads = [
            {"title": ""},
            {"title": "   "},
            {"title": "x" * 101},
            {"title": "Valid", "description": "x" * 2001},
            {"title": "Bad\nTitle"},
            {"title": "Valid", "description": "Bad\u0000description"},
            {"id": "CASE-2000-000001", "title": "Client ID"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/cases", json=payload).status_code, 422)

    def test_get_unknown_and_existing_case(self):
        self.assertEqual(self.client.get("/api/cases/CASE-2099-999999").status_code, 404)
        case = self.create_case().json()
        response = self.client.get(f"/api/cases/{case['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["evidence_count"], 0)
        self.assertEqual(response.json()["evidence_by_media_type"]["image"], 0)

    def test_list_cases_supports_search_status_and_pagination(self):
        first = self.create_case("Alpha investigation").json()
        self.create_case("Beta investigation")
        response = self.client.get("/api/cases", params={"q": first["id"], "status": "Open", "limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["title"], "Alpha investigation")

    def test_case_persists_for_a_fresh_repository_and_app(self):
        case = self.create_case().json()
        fresh_repository = CaseRepository(self.database_path)
        fresh_app = FastAPI()
        fresh_app.include_router(create_cases_router(fresh_repository), prefix="/api")
        with TestClient(fresh_app) as fresh_client:
            response = fresh_client.get(f"/api/cases/{case['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Case one")

    def test_sequential_and_concurrent_case_ids_are_unique(self):
        sequential = [self.create_case(f"Sequential {index}").json()["id"] for index in range(3)]

        def create(index):
            return self.repository.create_case(f"Concurrent {index}", None, "Test analyst")["id"]

        with ThreadPoolExecutor(max_workers=6) as executor:
            concurrent = list(executor.map(create, range(12)))
        identifiers = sequential + concurrent
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(re.match(r"^CASE-\d{4}-\d{6}$", item) for item in identifiers))

    def test_register_list_filter_and_duplicate_hash(self):
        case_id = self.create_case().json()["id"]
        first = self.client.post(
            f"/api/cases/{case_id}/evidence",
            json={
                "filename": "first.png",
                "media_type": "image",
                "role": "Evidence",
                "size_bytes": 12,
                "sha256": SHA_A,
            },
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["evidence_id"], "EVID-1")
        self.assertFalse(first.json()["preserved"])
        self.assertEqual(first.json()["hash_source"], "client_declared")
        self.assertIsNone(first.json()["preserved_evidence_id"])
        second = self.client.post(
            f"/api/cases/{case_id}/evidence",
            json={
                "evidence_id": "REF-7",
                "filename": "reference.png",
                "media_type": "image",
                "role": "Reference",
                "size_bytes": 14,
                "sha256": SHA_A,
            },
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["duplicate_hash_of"], ["EVID-1"])
        filtered = self.client.get(
            f"/api/cases/{case_id}/evidence", params={"role": "Reference", "media_type": "image"}
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["total"], 1)
        self.assertEqual(filtered.json()["items"][0]["evidence_id"], "REF-7")
        detail = self.client.get(f"/api/cases/{case_id}").json()
        self.assertEqual(detail["evidence_count"], 2)
        self.assertEqual(detail["evidence_by_media_type"]["image"], 2)

    def test_evidence_errors_are_explicit(self):
        payload = {
            "evidence_id": "EVID-9",
            "filename": "file.wav",
            "media_type": "audio",
            "role": "Evidence",
            "size_bytes": 0,
            "sha256": SHA_B,
        }
        unknown = self.client.post("/api/cases/CASE-2099-999999/evidence", json=payload)
        self.assertEqual(unknown.status_code, 404)
        case_id = self.create_case().json()["id"]
        self.assertEqual(self.client.post(f"/api/cases/{case_id}/evidence", json=payload).status_code, 201)
        self.assertEqual(self.client.post(f"/api/cases/{case_id}/evidence", json=payload).status_code, 409)
        bad_hash = {**payload, "evidence_id": "EVID-10", "sha256": "ABC"}
        self.assertEqual(self.client.post(f"/api/cases/{case_id}/evidence", json=bad_hash).status_code, 422)
        self.assertEqual(self.client.get("/api/cases/CASE-2099-999999/evidence").status_code, 404)

    def test_case_events_are_appended_for_both_actions(self):
        case_id = self.create_case().json()["id"]
        self.client.post(
            f"/api/cases/{case_id}/evidence",
            json={
                "filename": "file.mp4",
                "media_type": "video",
                "role": "Evidence",
                "size_bytes": 99,
                "sha256": SHA_A,
            },
        )
        events = self.repository.list_events(case_id)
        self.assertEqual([event["event_type"] for event in events], ["case.created", "evidence.registered"])
        self.assertFalse(events[1]["detail"]["preserved"])


if __name__ == "__main__":
    unittest.main()
