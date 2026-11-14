"""Verify an extracted Pratyaksh evidence package using Python's standard library.

Run from any directory: python3 /path/to/package/verify.py
Retain manifest SHA-256 separately before transfer for whole-package verification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def verify(root, expected_manifest=None):
    root = Path(root).resolve()
    raw = (root / "manifest.json").read_bytes()
    if expected_manifest and sha(raw) != expected_manifest.lower():
        raise ValueError("Manifest does not match the externally retained SHA-256")
    manifest = json.loads(raw)
    required = {"report.json", "report.pdf", "activity.json", "verify.py"}
    if not required.issubset(manifest["files"]):
        raise ValueError("Manifest is missing required records")
    for name, expected in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha(path.read_bytes()) != expected:
            raise ValueError("Missing, unsafe or changed package file: " + name)
    report = json.loads((root / "report.json").read_bytes())
    expected = report.pop("report_sha256")
    if canonical_hash(report) != expected or expected != manifest["report_sha256"]:
        raise ValueError("Report payload failed verification")
    if report["analysis_id"] != manifest["analysis_id"]:
        raise ValueError("Analysis identity mismatch")
    events = json.loads((root / "activity.json").read_bytes())
    previous = "0" * 64
    for sequence, entry in enumerate(events, 1):
        body = {key: value for key, value in entry.items() if key != "entry_hash"}
        if (body["sequence"] != sequence or body["case_id"] != report["case"]["id"]
                or body["previous_hash"] != previous or canonical_hash(body) != entry["entry_hash"]):
            raise ValueError("Provenance event chain failed verification")
        previous = entry["entry_hash"]
    sequence = report["integrity"]["anchor_sequence"]
    if (not 1 <= sequence <= len(events) or events[sequence-1]["entry_hash"] != report["integrity"]["anchor_hash"]
            or manifest["anchor_hash"] != report["integrity"]["anchor_hash"]):
        raise ValueError("Saved analysis anchor is absent or changed")
    for image in report["images"]:
        name = "originals/" + image["sha256"]
        if name not in manifest["files"] or manifest["files"][name] != image["sha256"]:
            raise ValueError("Original missing or hash mismatch: " + image["filename"])
    return {"analysis_id": report["analysis_id"], "originals": len(report["images"]),
            "events": len(events), "manifest_sha256": sha(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--expected-manifest", help="Manifest SHA-256 retained independently before transfer")
    args = parser.parse_args()
    try:
        result = verify(args.directory, args.expected_manifest)
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        print("FAILED:", error, file=sys.stderr)
        return 1
    print("VERIFIED:", json.dumps(result, indent=2))
    print("File integrity and internal consistency verified. This does not establish authenticity or authorship.")
    if not args.expected_manifest:
        print("No external anchor supplied: whole-package replacement cannot be ruled out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
