"""Import the supplied Pratyaksh automated-demo ZIP as a real local case.

The archive's filenames are treated as supplier-provided test labels.  The
importer computes its own hashes, preserves the original bytes, runs the
existing provenance comparison, and creates a report containing only measured
facts.  It does not turn a filename such as ``synthetic-voice`` into an ML
verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from cases.repository import CaseRepository  # noqa: E402
from provenance import analyze_images  # noqa: E402
from provenance_store import ProvenanceStore  # noqa: E402
from reports.store import ReportStore  # noqa: E402


CASE_TITLE = "Automated multimedia provenance demonstration"
CASE_MARKER = "PRATYAKSH-AUTOMATED-DEMO-V1"
ANALYST = "Demo examiner (self-declared)"
MANIFEST_PATH = Path(__file__).with_name("automated_demo_manifest.json")


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, tuple[str, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("case_marker") != CASE_MARKER:
        raise ValueError("Unsupported automated-demo manifest")
    records: dict[str, tuple[str, str, str]] = {}
    for item in payload.get("files", []):
        name = item.get("filename")
        media_type = item.get("media_type")
        role = item.get("role")
        digest = item.get("sha256")
        if (not isinstance(name, str) or name in records or media_type not in {"image", "audio", "video"}
                or role not in {"Evidence", "Reference", "Control"} or not isinstance(digest, str)
                or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest)):
            raise ValueError("Invalid automated-demo manifest record")
        records[name] = (media_type, role, digest)
    if not records:
        raise ValueError("Automated-demo manifest contains no files")
    return records


EXPECTED = load_manifest()


def read_archive(path: Path) -> list[tuple[str, bytes]]:
    if not path.is_file():
        raise SystemExit(f"Archive not found: {path}")
    with zipfile.ZipFile(path) as archive:
        files: dict[str, bytes] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1:
                raise SystemExit(f"Unsafe or unexpected archive path: {info.filename}")
            files[pure.name] = archive.read(info)
    if set(files) != set(EXPECTED):
        missing = sorted(set(EXPECTED) - set(files))
        extra = sorted(set(files) - set(EXPECTED))
        raise SystemExit(f"Archive contents differ from the expected case (missing={missing}, extra={extra})")
    for name, raw in files.items():
        actual = hashlib.sha256(raw).hexdigest()
        expected = EXPECTED[name][2]
        if actual != expected:
            raise SystemExit(f"Hash mismatch for {name}: expected {expected}, received {actual}")
    return [(name, files[name]) for name in EXPECTED]


def measured_finding(case_id: str, evidence: dict, sequence: int) -> dict:
    """Create an objective preservation finding, not a media-authenticity claim."""
    digest = evidence["sha256"]
    return {
        "schema_version": "1.1",
        "finding_id": f"F-{hashlib.sha256(f'{case_id}:{sequence}:integrity'.encode()).hexdigest()[:24]}",
        "run_id": f"RUN-{hashlib.sha256(f'{case_id}:intake'.encode()).hexdigest()[:24]}",
        "evidence_id": evidence["evidence_id"],
        "category": "integrity",
        "execution_status": "completed",
        "result": None,
        "observation": "The preserved bytes match the server-computed SHA-256 recorded at intake.",
        "method": "SHA-256 preservation verification",
        "method_version": "automated-demo-import-1.0",
        "scope": "Complete preserved file",
        "score": None,
        "location": None,
        "support_refs": [],
        "limitations": [
            "A matching hash shows that retained bytes have not changed; it does not prove the media is authentic.",
            "The supplier-provided filename is a test label, not an independently verified detector result.",
        ],
        "review_status": "unreviewed",
        "error": None,
        "details": {
            "kind": "integrity", "comparison": "match",
            "reference_sha256": digest, "current_sha256": digest,
        },
        "fixture": False,
    }


def relationship_finding(case_id: str, evidence: dict, relationship: dict, sequence: int) -> dict:
    exact = relationship["kind"] == "exact_copy"
    observation = relationship["explanation"]
    return {
        "schema_version": "1.1",
        "finding_id": f"F-{hashlib.sha256(f'{case_id}:{sequence}:relationship'.encode()).hexdigest()[:24]}",
        "run_id": f"RUN-{hashlib.sha256(f'{case_id}:provenance'.encode()).hexdigest()[:24]}",
        "evidence_id": evidence["evidence_id"],
        "category": "provenance",
        "execution_status": "completed",
        "result": "indicators_detected" if exact else "inconclusive",
        "observation": observation,
        "method": "SHA-256 exact comparison" if exact else "dHash candidate search with SIFT and RANSAC",
        "method_version": "automated-demo-provenance-1.0",
        "scope": "Relationship between preserved case items",
        "score": None,
        "location": None,
        "support_refs": [relationship["id"]],
        "limitations": [
            "A content relationship does not establish which file came first or who created it.",
            "A visual match can involve shared background or objects and is not a media-authenticity verdict.",
        ],
        "review_status": "unreviewed",
        "error": None,
        "details": {
            "kind": "provenance", "manifest": "not_assessed", "content_binding": "not_assessed",
            "signature": "not_assessed", "signer_trust": "not_assessed", "relationship": "candidate",
        },
        "fixture": False,
    }


def import_case(archive_path: Path, database: Path | None = None, provenance_dir: Path | None = None) -> dict:
    inputs = read_archive(archive_path)
    repository = CaseRepository(database)
    store = ProvenanceStore(provenance_dir)
    existing, _ = repository.list_cases(CASE_TITLE, None, 200, 0)
    case = next((item for item in existing if item["title"] == CASE_TITLE and CASE_MARKER in item["description"]), None)
    if case is not None:
        evidence = repository.list_evidence(case["id"])
        if {item["sha256"] for item in evidence} != {spec[2] for spec in EXPECTED.values()} or len(evidence) != len(EXPECTED):
            raise SystemExit(f"Existing case {case['id']} has different evidence; refusing to overwrite it.")
        revisions = ReportStore(repository).list(case["id"])
        return {"status": "already_imported", "case_id": case["id"], "evidence_count": len(evidence),
                "report_id": revisions[0]["report_id"] if revisions else None}

    description = (
        f"[{CASE_MARKER}] Prepared multimedia demonstration case imported from the supplied ZIP. "
        "Filenames describe intended test roles supplied with the archive; they are not independent ML conclusions. "
        "The application computes hashes, preserves originals, measures content relationships, and records limitations."
    )
    case = repository.create_case(CASE_TITLE, description, ANALYST)
    registered = []
    for name, raw in inputs:
        media_type, role, digest = EXPECTED[name]
        preserved_hash = store.preserve(raw)
        item = repository.register_evidence(case["id"], {
            "filename": name, "media_type": media_type, "role": role,
            "size_bytes": len(raw), "sha256": digest,
        }, ANALYST, preserved_hash=preserved_hash, receipt={
            "supplied_by": "User-supplied automated demonstration archive",
            "collection_reference": archive_path.name,
            "note": "Prepared test media. Filename role is a supplied label, not an independent forensic conclusion.",
        })
        registered.append(item)

    provenance = analyze_images(inputs)
    for image, item in zip(provenance["images"], registered):
        image["case_evidence_id"] = item["evidence_id"]
        image["case_intake"] = {
            "registered_at": item["registered_at"], "registered_by": item["registered_by"],
            "registered_by_verified": False, "receipt": item.get("receipt"),
        }
    provenance = store.save(provenance, inputs, case["id"], ANALYST, case["title"])

    for index, item in enumerate(registered, 1):
        repository.register_finding(measured_finding(case["id"], item, index), case["id"])
    by_image = {image["id"]: item for image, item in zip(provenance["images"], registered)}
    supported = [rel for rel in provenance["relationships"] if rel["kind"] in {"exact_copy", "matching_content"}]
    for index, relation in enumerate(supported, 1):
        repository.register_finding(
            relationship_finding(case["id"], by_image[relation["right_id"]], relation, index), case["id"]
        )

    report = ReportStore(repository).create(
        case["id"], ANALYST,
        questions="Which files are exact duplicates or visually related within this prepared demonstration set?",
        next_steps="Run modality-specific image, audio, and video detectors separately before making any authenticity claim.",
    )
    return {
        "status": "imported", "case_id": case["id"], "evidence_count": len(registered),
        "provenance_report_id": provenance["analysis_id"],
        "relationship_count": len(provenance["relationships"]),
        "measured_relationship_findings": len(supported),
        "report_id": report["snapshot"]["report_id"], "report_sha256": report["sha256"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to Pratyaksh-Automated-Demo.zip")
    parser.add_argument("--database", type=Path, help="Optional case database (defaults to backend/data/pratyaksh.db)")
    parser.add_argument("--provenance-dir", type=Path, help="Optional provenance store (defaults to backend/data/provenance)")
    args = parser.parse_args()
    print(json.dumps(import_case(args.archive, args.database, args.provenance_dir), indent=2, sort_keys=True))
