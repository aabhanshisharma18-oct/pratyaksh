"""Append-only report snapshots sourced exclusively from registered case records."""
import hashlib
import io
import json
import sqlite3
import uuid
import zipfile
from pathlib import Path

from cases.repository import CaseNotFoundError, utc_now
from .content import analyst_text, audit_snapshot
from .references import run_references
from .artifacts import capture_artifacts

REPORT_SECTIONS = ("methods", "evidence", "findings", "coverage", "notes", "limitations")
REQUIRED_SECTIONS = {"methods", "findings", "coverage", "limitations"}

CHANNELS = ("synthetic_media", "tampering", "integrity", "provenance")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


class ReportStore:
    def __init__(self, cases, database_path=None, run_reader=None, artifact_reader=None):
        self.cases = cases
        self.run_reader = run_reader
        self.artifact_reader = artifact_reader
        self.path = Path(database_path or cases.database_path)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS report_revisions (
                report_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
                revision INTEGER NOT NULL, snapshot BLOB NOT NULL,
                sha256 TEXT NOT NULL, UNIQUE(case_id, revision))""")
            db.execute("CREATE TABLE IF NOT EXISTS report_artifact_blobs (sha256 TEXT PRIMARY KEY, content BLOB NOT NULL)")

    def run_options(self, case_id):
        records = self.cases.list_findings(case_id)
        groups = {}
        for record in records:
            groups.setdefault(record["run_id"], []).append(record)
        with sqlite3.connect(self.cases.database_path) as db:
            has_runs = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'").fetchone()
            statuses = dict(db.execute("SELECT id, status FROM runs WHERE case_id=?", (case_id,)).fetchall()) if has_runs else {}
        options = []
        for run_id, findings in groups.items():
            states = [item["finding"].get("execution_status") for item in findings]
            status = statuses.get(run_id) or ("running" if any(s in ("queued", "running") for s in states)
                        else "completed" if all(s == "completed" for s in states)
                        else "partial" if "completed" in states else "failed")
            options.append({"run_id": run_id, "status": status,
                            "selectable": status in ("completed", "partial", "failed", "unsupported", "cancelled"),
                            "status_source": "run_record" if run_id in statuses else "registered_findings",
                            "finding_count": len(findings),
                            "evidence_ids": sorted({item["evidence_id"] for item in findings})})
        return options

    def create(self, case_id, preparer, run_ids=None, sections=None, questions=None, next_steps=None, include_artifacts=False):
        questions, next_steps = analyst_text(questions), analyst_text(next_steps)
        if sections is None:
            sections = list(REPORT_SECTIONS)
        if (len(set(sections)) != len(sections) or not set(sections).issubset(REPORT_SECTIONS)
                or not REQUIRED_SECTIONS.issubset(sections)):
            raise ValueError("Choose valid unique sections; methods, findings, coverage and limitations are required")
        sections = [section for section in REPORT_SECTIONS if section in sections]
        preparer = preparer.strip()
        if not preparer or len(preparer) > 200 or any(ord(c) < 32 for c in preparer):
            raise ValueError("Prepared by must contain 1–200 printable characters")
        case = self.cases.get_case(case_id)
        if case is None:
            raise CaseNotFoundError(case_id)
        evidence = self.cases.list_evidence(case_id)
        records = self.cases.list_findings(case_id)
        registered_count = len(records)
        selection = None
        if run_ids is not None:
            if not run_ids or len(set(run_ids)) != len(run_ids):
                raise ValueError("Select at least one unique run")
            available = {item["run_id"]: item for item in self.run_options(case_id)}
            if any(run_id not in available or not available[run_id]["selectable"] for run_id in run_ids):
                raise ValueError("Selected runs must belong to this case and have finished")
            selection = sorted(run_ids)
            records = [item for item in records if item["run_id"] in selection]
        notes = {r["finding_id"]: self.cases.list_finding_notes(r["finding_id"]) for r in records}
        coverage = [{"evidence_id": e["evidence_id"], "category": channel,
                     "finding_ids": [r["finding_id"] for r in records
                                     if r["evidence_id"] == e["evidence_id"] and r["finding"]["category"] == channel],
                     "status": "recorded" if any(r["evidence_id"] == e["evidence_id"] and
                               r["finding"]["category"] == channel for r in records) else "not_assessed"}
                    for e in evidence for channel in CHANNELS]
        audit = audit_snapshot(self.cases, case_id)
        references = run_references(case_id, records, self.run_reader)
        blobs = capture_artifacts(case_id, references, self.artifact_reader) if include_artifacts else {}
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            revision = db.execute("SELECT COALESCE(MAX(revision), 0)+1 FROM report_revisions WHERE case_id=?", (case_id,)).fetchone()[0]
            snapshot = {"schema_version": "d5.7", "report_id": "RPT-" + uuid.uuid4().hex,
                        "revision": revision, "generated_at": utc_now(), "case": case,
                        "preparer": preparer, "preparer_verified": False,
                        "evidence": evidence, "findings": records, "review_notes": notes,
                        "coverage": coverage, "review_status": "unreviewed", "sections": sections,
                        "analyst_context": {"questions": questions, "next_steps": next_steps,
                                            "author": preparer, "author_verified": False},
                        "audit_summary": audit,
                        "source_references": references,
                        "package_policy": {"include_artifacts_requested": include_artifacts,
                                           "original_media_included": False,
                                           "verified_artifact_count": len(blobs)},
                        "run_selection": {"mode": "selected" if selection is not None else "all_registered",
                                          "run_ids": selection if selection is not None else sorted({r["run_id"] for r in records}),
                                          "excluded_finding_count": registered_count - len(records)},
                        "fixture": any(r["finding"].get("fixture", False) for r in records),
                        "limitations": ["Only registered case findings are included; no inference runs during report creation.",
                                        "Missing findings mean not assessed, never authentic or cleared.",
                                        "When runs are selected, coverage describes only those runs; excluded runs were not reviewed in this report.",
                                        "Execution failures and inconclusive results remain as recorded.",
                                        "Original media is excluded. Only explicitly requested, hash-verified artifact bytes may be packaged.",
                                        "Hashes detect changes relative to this export; they are not signatures or external timestamps.",
                                        "Source records are collected sequentially; this is not a transaction-wide case snapshot."]}
            raw = canonical(snapshot)
            digest = hashlib.sha256(raw).hexdigest()
            for artifact_hash, content in blobs.items():
                db.execute("INSERT OR IGNORE INTO report_artifact_blobs VALUES (?, ?)", (artifact_hash, content))
            db.execute("INSERT INTO report_revisions VALUES (?, ?, ?, ?, ?)",
                       (snapshot["report_id"], case_id, revision, raw, digest))
        return {"snapshot": snapshot, "sha256": digest}

    def get(self, report_id):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT snapshot, sha256 FROM report_revisions WHERE report_id=?", (report_id,)).fetchone()
        if row is None:
            raise KeyError(report_id)
        if hashlib.sha256(row[0]).hexdigest() != row[1]:
            raise ValueError("Saved report failed SHA-256 verification")
        return {"snapshot": json.loads(row[0]), "sha256": row[1]}

    def review(self, report_id, reviewer, status, note):
        reviewer, note = reviewer.strip(), note.strip()
        if (not reviewer or len(reviewer) > 200
                or any(ord(c) < 32 or ord(c) == 127 for c in reviewer)):
            raise ValueError("Reviewer must contain 1–200 printable characters")
        if status not in ("reviewed", "questioned"):
            raise ValueError("Choose reviewed or questioned")
        if (not note or len(note) > 2000
                or any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in note)):
            raise ValueError("A review note of 1–2000 characters is required")
        source = self.get(report_id)
        # get() deserializes a fresh copy. Never reload mutable case/finding data.
        snapshot = source["snapshot"]
        now = utc_now()
        snapshot["prepared_at"] = snapshot.get("prepared_at", snapshot["generated_at"])
        snapshot["schema_version"] = "d5.7" if "package_policy" in snapshot else "d5.6" if "source_references" in snapshot else "d5.5" if "audit_summary" in snapshot else "d5.4"
        snapshot["parent_report_id"] = report_id
        snapshot["parent_report_sha256"] = source["sha256"]
        snapshot["report_id"] = "RPT-" + uuid.uuid4().hex
        snapshot["generated_at"] = now
        snapshot["review_status"] = status
        snapshot["review_history"] = [*snapshot.get("review_history", []), {
            "reviewer": reviewer, "reviewer_verified": False, "status": status,
            "note": note, "reviewed_at": now, "source_report_id": report_id,
            "source_report_sha256": source["sha256"],
        }]
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            snapshot["revision"] = db.execute(
                "SELECT COALESCE(MAX(revision), 0)+1 FROM report_revisions WHERE case_id=?",
                (snapshot["case"]["id"],)).fetchone()[0]
            raw = canonical(snapshot)
            digest = hashlib.sha256(raw).hexdigest()
            db.execute("INSERT INTO report_revisions VALUES (?, ?, ?, ?, ?)",
                       (snapshot["report_id"], snapshot["case"]["id"], snapshot["revision"], raw, digest))
        return {"snapshot": snapshot, "sha256": digest}

    def list(self, case_id):
        if self.cases.get_case(case_id) is None:
            raise CaseNotFoundError(case_id)
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT report_id, revision, sha256 FROM report_revisions WHERE case_id=? ORDER BY revision DESC", (case_id,)).fetchall()
        return [{"report_id": r[0], "revision": r[1], "sha256": r[2]} for r in rows]

    def export(self, report_id):
        saved = self.get(report_id)
        raw = canonical(saved["snapshot"])
        files = {"report.json": raw}
        for item in saved["snapshot"].get("source_references", {}).get("artifacts", []):
            if not item.get("bytes_included"):
                continue
            digest = item["metadata"]["sha256"]
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("Invalid saved artifact digest")
            with sqlite3.connect(self.path) as db:
                row = db.execute("SELECT content FROM report_artifact_blobs WHERE sha256=?", (digest,)).fetchone()
            if row is None or hashlib.sha256(row[0]).hexdigest() != digest:
                raise ValueError("Saved artifact failed SHA-256 verification")
            files[f"artifacts/{digest}.bin"] = row[0]
        manifest = canonical({"schema_version": "d5.1", "report_id": report_id,
                              "files": [{"path": path, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
                                        for path, content in sorted(files.items())],
                              "original_media_included": False, "artifact_bytes_included": len(files) > 1})
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path, content in files.items():
                bundle.writestr(path, content)
            bundle.writestr("manifest.json", manifest)
        return output.getvalue()
