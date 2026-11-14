import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from fastapi import HTTPException
from automation import CaseAutomation, archive_members, classify
from cases.repository import CaseRepository
from runs.repository import RunRepository


def png():
    stream = io.BytesIO()
    Image.new("RGB", (64, 64), "gray").save(stream, "PNG")
    return stream.getvalue()


def zipped(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, raw in files:
            archive.writestr(name, raw)
    return stream.getvalue()


class AutomationTests(unittest.TestCase):
    def test_rejects_traversal_and_duplicate_paths(self):
        for names in (["../outside.png"], ["/outside.png"], ["same.png", "same.png"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                archive_members(zipped([(name, png()) for name in names]))

    def test_classifies_decoded_image_without_trusting_extension(self):
        self.assertEqual(classify(png()), "image")
        self.assertIsNone(classify(b"ordinary document text"))

    def service(self, root):
        cases = CaseRepository(root / "cases.sqlite")
        runs = RunRepository(cases.database_path)

        def worker(run_id):
            run = runs.get_run(run_id)
            for check in run["requested_checks"]:
                finding = {
                    "schema_version": "1.1", "finding_id": run_id + "-" + check,
                    "run_id": run_id, "evidence_id": run["evidence_id"],
                    "category": "synthetic_media", "execution_status": "completed",
                    "result": "inconclusive", "observation": "Integration test observation",
                    "method": "Test worker", "method_version": "1", "scope": "Test input",
                    "score": None, "location": None, "support_refs": [], "limitations": [],
                    "review_status": "unreviewed", "fixture": False,
                }
                runs.append_event(run_id, check, "check.completed", "completed", {"findings": [finding]})

        service = CaseAutomation(cases, runs, worker,
                                 lambda *args: {"checked": True}, lambda *args: {"relationships": 1})
        # Keep deterministic control over queued execution in these tests.
        service.pool.shutdown(wait=True)
        service.pool = type("Queue", (), {"submit": lambda *args: None})()
        return service

    def test_upload_is_idempotent_and_resumes_without_duplicate_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(Path(folder))
            raw = zipped([("image-with-wrong-extension.txt", png()), ("copy.png", png())])
            with patch("automation.ProvenanceStore") as storage:
                blob = Path(folder) / "original"
                blob.write_bytes(png())
                storage.return_value.preserve.return_value = "a" * 64
                storage.return_value.blob_path.return_value = blob
                job = service.submit(raw, "Test", "", "Tester", "request-one")
                same = service.submit(raw, "Test", "", "Tester", "request-one")
                self.assertEqual(job["id"], same["id"])
                with self.assertRaises(HTTPException):
                    service.submit(raw, "Another title", "", "Tester", "request-one")
                service.run(job["id"])
                result = service.get(job["id"])
                self.assertEqual(result["status"], "completed", result)
                self.assertEqual(len(service.cases.list_evidence(job["case_id"])), 2)
                self.assertEqual(result["report"]["status"], "completed")
                service.run(job["id"])
                self.assertEqual(len(service.cases.list_evidence(job["case_id"])), 2)

    def test_unsupported_files_are_visible_and_failure_does_not_block_other_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(Path(folder))
            raw = zipped([("image.png", png()), ("readme.txt", b"unsupported note")])
            with patch("automation.ProvenanceStore") as storage:
                blob = Path(folder) / "original"
                blob.write_bytes(png())
                storage.return_value.preserve.return_value = "a" * 64
                storage.return_value.blob_path.return_value = blob
                service.authenticate = lambda *args: (_ for _ in ()).throw(ValueError("metadata unavailable"))
                job = service.submit(raw, "Partial case", "", "Tester", "partial")
                service.run(job["id"])
                result = service.get(job["id"])
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["files"][1]["status"], "skipped")
                self.assertEqual(result["files"][0]["authentication"]["status"], "failed")
                self.assertEqual(result["report"]["status"], "completed")

    def test_restart_marks_pending_job_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(Path(folder))
            job = service.submit(zipped([("image.png", png())]), "Case", "", "Tester", "restart")
            replacement = CaseAutomation(service.cases, service.runs, service.worker,
                                         service.authenticate, service.relate)
            try:
                self.assertEqual(replacement.get(job["id"])["status"], "interrupted")
            finally:
                replacement.pool.shutdown()


if __name__ == "__main__":
    unittest.main()
