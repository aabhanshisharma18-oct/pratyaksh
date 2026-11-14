"""Separate persistent provenance records and hash-chained case logs."""
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


class ProvenanceStore:
    def __init__(self, root=None):
        self.root = Path(root or os.getenv("PRATYAKSH_PROVENANCE_DIR",
                         Path(__file__).parent / "data" / "provenance"))
        self.blobs = self.root / "originals"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "provenance.sqlite3"
        db = self.connect()
        try:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS provenance_reports(
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    body TEXT NOT NULL, body_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS provenance_case_context(
                    case_id TEXT PRIMARY KEY, title TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS provenance_files(
                    report_id TEXT NOT NULL, image_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                    body TEXT NOT NULL, PRIMARY KEY(report_id,image_id));
                CREATE TABLE IF NOT EXISTS provenance_edges(
                    report_id TEXT NOT NULL, edge_id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(report_id,edge_id));
                CREATE TABLE IF NOT EXISTS provenance_events(
                    case_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    body TEXT NOT NULL, entry_hash TEXT NOT NULL,
                    PRIMARY KEY(case_id, sequence));
            """)
            db.commit()
        finally:
            db.close()

    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def blob_path(self, hash_value):
        if not re.fullmatch("[a-f0-9]{64}", hash_value):
            raise ValueError("Invalid SHA-256")
        return self.blobs / hash_value

    def preserve(self, raw):
        hash_value = hashlib.sha256(raw).hexdigest()
        destination = self.blob_path(hash_value)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != hash_value:
                raise ValueError("A preserved original failed hash verification. Intake stopped.")
            return hash_value
        fd, name = tempfile.mkstemp(prefix=".intake-", dir=self.blobs)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o400)
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if hashlib.sha256(destination.read_bytes()).hexdigest() != hash_value:
                    raise ValueError("Concurrent original hash mismatch")
        finally:
            temporary.unlink(missing_ok=True)
        return hash_value

    def validate_chain(self, db, case_id):
        previous = "0" * 64
        rows = db.execute("SELECT body,entry_hash FROM provenance_events WHERE case_id=? ORDER BY sequence", (case_id,)).fetchall()
        for sequence, row in enumerate(rows, 1):
            body = json.loads(row["body"])
            if (body.get("case_id") != case_id or body.get("sequence") != sequence
                    or body.get("previous_hash") != previous or digest(body) != row["entry_hash"]):
                raise ValueError("Provenance chain failed verification. Further recording stopped.")
            previous = row["entry_hash"]
        anchors = {index + 1: row["entry_hash"] for index, row in enumerate(rows)}
        for snapshot in db.execute("SELECT body,body_hash FROM provenance_reports WHERE case_id=?", (case_id,)).fetchall():
            report = json.loads(snapshot["body"])
            if (digest(report) != snapshot["body_hash"] or
                    anchors.get(report["integrity"]["anchor_sequence"]) != report["integrity"]["anchor_hash"]):
                raise ValueError("Saved analysis anchor failed verification. Further recording stopped.")

    def append(self, db, case_id, actor, action, detail):
        self.validate_chain(db, case_id)
        row = db.execute("SELECT sequence,entry_hash FROM provenance_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1",
                         (case_id,)).fetchone()
        body = {"case_id": case_id, "sequence": row["sequence"] + 1 if row else 1,
                "actor": actor, "timestamp": now(), "action": action, "detail": detail,
                "previous_hash": row["entry_hash"] if row else "0" * 64}
        entry_hash = digest(body)
        db.execute("INSERT INTO provenance_events VALUES (?,?,?,?)",
                   (case_id, body["sequence"], canonical(body).decode(), entry_hash))
        return {**body, "entry_hash": entry_hash}

    def save(self, report, inputs, case_id, actor, title):
        for _, raw in inputs:
            self.preserve(raw)
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            for image in report["images"]:
                self.append(db, case_id, actor, "original_preserved",
                            {"analysis_id": report["analysis_id"], "image_id": image["id"],
                             "filename": image["filename"], "sha256": image["sha256"]})
            anchor = self.append(db, case_id, actor, "comparison_completed",
                                 {"analysis_id": report["analysis_id"], "connections": len(report["relationships"])})
            report["case"] = {"id": case_id, "title": title, "analyst": actor,
                              "analyst_identity": "Self-declared"}
            report["integrity"] = {"anchor_sequence": anchor["sequence"], "anchor_hash": anchor["entry_hash"],
                                   "storage": "Original files stored read-only, keyed by SHA-256.",
                                   "log_scope": "Provenance intake, analysis and export events. Operational case activity is maintained separately.",
                                   "limitations": "Hash chaining detects edits against a retained anchor. A privileged attacker can rewrite the entire chain unless an external anchor is retained."}
            self.index_report(db, report)
            body_hash = digest(report)
            db.execute("INSERT INTO provenance_reports VALUES (?,?,?,?,?)",
                       (report["analysis_id"], case_id, now(), canonical(report).decode(), body_hash))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return {**report, "report_sha256": body_hash}

    def get(self, report_id):
        db = self.connect()
        try:
            row = db.execute("SELECT body,body_hash FROM provenance_reports WHERE id=?", (report_id,)).fetchone()
        finally:
            db.close()
        if not row:
            raise KeyError("Comparison report not found")
        report = json.loads(row["body"])
        if digest(report) != row["body_hash"]:
            raise ValueError("Stored report failed hash verification")
        return {**report, "report_sha256": row["body_hash"]}

    def events(self, case_id):
        db = self.connect()
        try:
            rows = db.execute("SELECT body,entry_hash FROM provenance_events WHERE case_id=? ORDER BY sequence", (case_id,)).fetchall()
            return [{**json.loads(row["body"]), "entry_hash": row["entry_hash"]} for row in rows]
        finally:
            db.close()

    def verify(self, report, retained_anchor=None):
        try:
            entries = self.events(report["case"]["id"])
            chain_valid = True
        except (ValueError, TypeError):
            entries = []
            chain_valid = False
        previous = "0" * 64
        for sequence, entry in enumerate(entries, 1):
            body = {key: value for key, value in entry.items() if key != "entry_hash"}
            if (body.get("case_id") != report["case"]["id"] or body.get("sequence") != sequence or body.get("previous_hash") != previous or digest(body) != entry["entry_hash"]):
                chain_valid = False
            previous = entry["entry_hash"]
        index = report["integrity"]["anchor_sequence"] - 1
        anchor = entries[index]["entry_hash"] if index < len(entries) else None
        expected = retained_anchor or report["integrity"]["anchor_hash"]
        files = []
        for image in report["images"]:
            path = self.blob_path(image["sha256"])
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            files.append({"image_id": image["id"], "filename": image["filename"],
                          "expected": image["sha256"], "actual": actual, "matches": actual == image["sha256"]})
        return {"chain_valid": chain_valid, "anchor_matches": anchor == expected,
                "retained_anchor": expected, "files": files,
                "all_originals_match": all(item["matches"] for item in files)}

    def log_action(self, report, action, detail):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            entry = self.append(db, report["case"]["id"], report["case"]["analyst"], action, detail)
            db.commit()
            return entry
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def revision(self, report, image_id=None, signals=None, review=None):
        import uuid
        previous_id = report["analysis_id"]
        report = json.loads(json.dumps(report))
        report.pop("report_sha256", None)
        report["parent_analysis_id"] = previous_id
        report["analysis_id"] = "PROV-" + uuid.uuid4().hex
        report["analyzed_at"] = now()
        if review is not None:
            report.setdefault("review_notes", []).append(review)
        else:
            image = next(item for item in report["images"] if item["id"] == image_id)
            image["detector_signals"] = signals
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            anchor = self.append(db, report["case"]["id"], review["author"] if review is not None else report["case"]["analyst"], "reviewer_note_recorded" if review is not None else "detector_signals_recorded",
                                 {"image_id": image_id, "parent_analysis_id": previous_id,
                                  "analysis_id": report["analysis_id"], "record_sha256": digest(review if review is not None else signals)})
            report["integrity"]["anchor_sequence"] = anchor["sequence"]
            report["integrity"]["anchor_hash"] = anchor["entry_hash"]
            self.index_report(db, report)
            value = digest(report)
            db.execute("INSERT INTO provenance_reports VALUES(?,?,?,?,?)",
                       (report["analysis_id"],report["case"]["id"],now(),canonical(report).decode(),value))
            db.commit()
            return {**report,"report_sha256":value}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def index_report(self, db, report):
        db.execute("INSERT INTO provenance_case_context VALUES(?,?) ON CONFLICT(case_id) DO UPDATE SET title=excluded.title",
                   (report["case"]["id"],report["case"]["title"]))
        for image in report["images"]:
            db.execute("INSERT INTO provenance_files VALUES(?,?,?,?)",
                       (report["analysis_id"],image["id"],image["sha256"],canonical(image).decode()))
        for edge in report["relationships"]:
            db.execute("INSERT INTO provenance_edges VALUES(?,?,?)",
                       (report["analysis_id"],edge["id"],canonical(edge).decode()))
