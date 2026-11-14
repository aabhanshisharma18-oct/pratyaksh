"""D5 adapter for bounded, case-bound D2 derivative exports."""
import hashlib
from pathlib import Path

from d2.db import AnalysisRun, Derivative, Evidence

MAX_ARTIFACT_BYTES = 10 * 1024 * 1024
MAX_PACKAGE_ARTIFACT_BYTES = 50 * 1024 * 1024


def verified_file(path, root, expected_hash, expected_size=None, limit=MAX_ARTIFACT_BYTES):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root):
        raise ValueError("path_outside_storage")
    digest, size, chunks = hashlib.sha256(), 0, []
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError("size_limit")
            digest.update(chunk)
            # Original bytes are checked by hash but never collected for export.
            if expected_size is None:
                chunks.append(chunk)
    if digest.hexdigest() != expected_hash or (expected_size is not None and size != expected_size):
        raise ValueError("hash_mismatch")
    return b"".join(chunks)


class D2ReportArtifacts:
    def __init__(self, services, cases):
        self.services, self.cases = services, cases

    def read(self, case_id, reference):
        core = next((item for item in self.cases.list_evidence(case_id)
                     if item["evidence_id"] == reference["evidence_id"]), None)
        with self.services.database.session() as db:
            run = db.get(AnalysisRun, reference["run_id"])
            derivative = db.get(Derivative, reference["reference"])
            if not run or not derivative:
                raise ValueError("d2_run_or_derivative_not_found")
            parent = db.get(Evidence, derivative.evidence_id)
            if (not core or not parent or parent.case_id != case_id
                    or run.evidence_id != parent.id or derivative.id not in run.artifacts
                    or core["sha256"] != parent.sha256 or core["size_bytes"] != parent.byte_size):
                raise ValueError("case_evidence_or_run_mismatch")
            verified_file(parent.storage_path, self.services.config.originals, parent.sha256,
                          parent.byte_size, self.services.config.max_upload_bytes)
            raw = verified_file(derivative.storage_path, self.services.config.derivatives, derivative.sha256)
            return raw, {"derivative_id": derivative.id, "kind": derivative.kind,
                         "sha256": derivative.sha256, "size_bytes": len(raw),
                         "parent_sha256": parent.sha256, "source": "d2_registered_derivative"}


def capture_artifacts(case_id, references, reader):
    blobs, total = {}, 0
    for item in references["artifacts"]:
        try:
            if reader is None:
                raise ValueError("artifact_adapter_unavailable")
            raw, metadata = reader.read(case_id, item)
            digest = hashlib.sha256(raw).hexdigest()
            if len(raw) > MAX_ARTIFACT_BYTES:
                raise ValueError("size_limit")
            if metadata.get("sha256") != digest:
                raise ValueError("hash_mismatch")
            if digest not in blobs:
                if total + len(raw) > MAX_PACKAGE_ARTIFACT_BYTES:
                    raise ValueError("package_size_limit")
                blobs[digest] = raw
                total += len(raw)
            item.update(status="verified", metadata=metadata, bytes_verified=True,
                        bytes_included=True, zip_path=f"artifacts/{digest}.bin", verification="hash_match")
        except (ValueError, OSError) as error:
            # Store stable status codes, never internal paths from OSError text.
            code = str(error) if isinstance(error, ValueError) else "artifact_file_unavailable"
            item.update(verification=code, bytes_verified=False, bytes_included=False)
    return blobs
