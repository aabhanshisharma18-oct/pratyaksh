import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from cases.repository import CaseRepository
from d2.db import D2Database, Evidence, Derivative, AnalysisRun
from reports.artifacts import D2ReportArtifacts
from reports.store import ReportStore


class ReportArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.cases = CaseRepository(root / "cases.db")
        self.case = self.cases.create_case("Artifact test", "No inference", "Bhumi")
        self.originals, self.derivatives = root / "originals", root / "derivatives"
        self.originals.mkdir(); self.derivatives.mkdir()
        self.original = self.originals / "test.bin"
        self.original.write_bytes(b"test original bytes")
        self.artifact = self.derivatives / "test.bin"
        self.raw = b"illustrative test artifact bytes"
        self.artifact.write_bytes(self.raw)
        self.digest = hashlib.sha256(self.raw).hexdigest()
        parent_hash = hashlib.sha256(self.original.read_bytes()).hexdigest()
        core = self.cases.register_evidence(self.case["id"], {"filename": "test.bin", "media_type": "image",
            "role": "Evidence", "size_bytes": self.original.stat().st_size, "sha256": parent_hash}, "Bhumi")
        self.database = D2Database(root / "d2.db")
        with self.database.session() as db:
            db.add(Evidence(id="D2-parent", case_id=self.case["id"], original_filename="test.bin",
                storage_path=str(self.original), sha256=parent_hash, byte_size=self.original.stat().st_size,
                uploader_identity="Test actor"))
            db.flush()
            db.add(Derivative(id="D2-artifact", evidence_id="D2-parent", kind="test-only", storage_path=str(self.artifact),
                transformation="test fixture", parameters={}, tool_versions={}, sha256=self.digest))
            db.add(AnalysisRun(id="D2RUN-test", evidence_id="D2-parent", method="Test method", method_version="test-1",
                format_support="Supported", decoding="Completed", analysis="Completed", parameters={}, findings={},
                interpretation="Test only", limitations=["No inference"], artifacts=["D2-artifact"]))
        finding = {"finding_id": "F-artifact", "run_id": "D2RUN-test", "evidence_id": core["evidence_id"],
                   "category": "tampering", "execution_status": "completed", "fixture": True, "support_refs": ["D2-artifact"]}
        self.cases.register_finding(finding, self.case["id"])
        services = SimpleNamespace(database=self.database, config=SimpleNamespace(originals=self.originals,
            derivatives=self.derivatives, max_upload_bytes=1024))
        self.store = ReportStore(self.cases, artifact_reader=D2ReportArtifacts(services, self.cases))

    def test_verified_artifact_is_frozen_and_exported_with_hash_manifest(self):
        saved = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)
        record = saved["snapshot"]["source_references"]["artifacts"][0]
        self.assertTrue(record["bytes_included"])
        self.assertEqual(record["status"], "verified")
        # Later source deletion does not change the immutable exported package.
        self.artifact.unlink(); self.original.unlink()
        reviewed = self.store.review(saved["snapshot"]["report_id"], "Bhumi", "reviewed", "Verified test reference")
        for report in (saved, reviewed):
            with zipfile.ZipFile(io.BytesIO(self.store.export(report["snapshot"]["report_id"]))) as bundle:
                self.assertEqual(bundle.read(record["zip_path"]), self.raw)
                manifest = json.loads(bundle.read("manifest.json"))
                self.assertTrue(manifest["artifact_bytes_included"])
                self.assertFalse(manifest["original_media_included"])
                for item in manifest["files"]:
                    self.assertEqual(hashlib.sha256(bundle.read(item["path"])).hexdigest(), item["sha256"])
                    self.assertEqual(len(bundle.read(item["path"])), item["size_bytes"])
                self.assertEqual(len(bundle.namelist()), 3)

    def test_default_policy_does_not_copy_artifact_bytes(self):
        self.artifact.unlink()
        report = self.store.create(self.case["id"], "Bhumi")["snapshot"]
        self.assertFalse(report["package_policy"]["include_artifacts_requested"])
        self.assertFalse(report["source_references"]["artifacts"][0]["bytes_included"])

    def test_mismatched_bytes_are_excluded(self):
        self.artifact.write_bytes(b"changed")
        saved = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)
        record = saved["snapshot"]["source_references"]["artifacts"][0]
        self.assertEqual(record["verification"], "hash_mismatch")
        self.assertFalse(record["bytes_included"])

    def test_changed_original_blocks_its_derivative(self):
        self.original.write_bytes(b"changed original")
        report = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)["snapshot"]
        record = report["source_references"]["artifacts"][0]
        self.assertEqual(record["verification"], "hash_mismatch")
        self.assertFalse(record["bytes_included"])

    def test_wrong_case_and_run_membership_are_rejected(self):
        with self.database.session() as db:
            db.get(Evidence, "D2-parent").case_id = "OTHER-CASE"
        report = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)["snapshot"]
        self.assertEqual(report["source_references"]["artifacts"][0]["verification"], "case_evidence_or_run_mismatch")
        with self.database.session() as db:
            db.get(Evidence, "D2-parent").case_id = self.case["id"]
            db.get(AnalysisRun, "D2RUN-test").artifacts = []
        report = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)["snapshot"]
        self.assertEqual(report["package_policy"]["verified_artifact_count"], 0)

    def test_path_outside_derivative_storage_is_not_read(self):
        with self.database.session() as db:
            db.get(Derivative, "D2-artifact").storage_path = str(self.original)
        report = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)["snapshot"]
        self.assertEqual(report["source_references"]["artifacts"][0]["verification"], "path_outside_storage")

    def test_corrupt_frozen_blob_blocks_export(self):
        saved = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)
        with sqlite3.connect(self.cases.database_path) as db:
            db.execute("UPDATE report_artifact_blobs SET content=?", (b"corrupt",))
        with self.assertRaisesRegex(ValueError, "Saved artifact failed"):
            self.store.export(saved["snapshot"]["report_id"])

    def test_missing_parent_and_artifact_files_are_excluded(self):
        self.original.unlink()
        report = self.store.create(self.case["id"], "Bhumi", include_artifacts=True)["snapshot"]
        self.assertEqual(report["source_references"]["artifacts"][0]["verification"], "artifact_file_unavailable")
        self.assertEqual(report["package_policy"]["verified_artifact_count"], 0)

    def test_artifact_size_limit_is_enforced(self):
        from unittest.mock import patch
        from reports.artifacts import verified_file, capture_artifacts
        with self.assertRaisesRegex(ValueError, "size_limit"):
            verified_file(self.artifact, self.derivatives, self.digest, limit=1)
        with patch("reports.artifacts.MAX_PACKAGE_ARTIFACT_BYTES", 1):
            references={"artifacts":[{"reference":"D2-artifact","evidence_id":self.cases.list_evidence(self.case["id"])[0]["evidence_id"],"run_id":"D2RUN-test"}]}
            blobs=capture_artifacts(self.case["id"], references, self.store.artifact_reader)
        self.assertEqual(blobs, {})
        self.assertEqual(references["artifacts"][0]["verification"], "package_size_limit")
