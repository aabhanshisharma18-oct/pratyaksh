from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cases.repository import CaseRepository


TERMINAL_CHECK_STATUSES = {"completed", "failed", "timeout", "unsupported", "unexamined"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def aggregate_run_status(statuses: Iterable[str]) -> str:
    """Derive one honest run status from the latest state of every requested check."""
    values = list(statuses)
    if not values or all(value == "queued" for value in values):
        return "queued"
    if any(value in {"queued", "running"} for value in values):
        return "running"
    completed = sum(value == "completed" for value in values)
    if completed == len(values):
        return "completed"
    if completed:
        return "partial"
    if any(value == "unexamined" for value in values):
        return "partial"
    return "failed"


class RunNotFoundError(LookupError):
    pass


class EvidenceNotFoundError(LookupError):
    pass


class AmbiguousEvidenceError(ValueError):
    pass


class InvalidRetryError(ValueError):
    pass


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class RunRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','partial','failed','unsupported','cancelled')),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    retry_of_run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
                    attempt INTEGER NOT NULL CHECK(attempt >= 1),
                    kind TEXT NOT NULL CHECK(kind IN ('image','audio','video')),
                    requested_checks_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    error_json TEXT,
                    input_path TEXT,
                    FOREIGN KEY (case_id, evidence_id) REFERENCES case_evidence(case_id, evidence_id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE RESTRICT,
                    seq INTEGER NOT NULL CHECK(seq >= 1),
                    timestamp TEXT NOT NULL,
                    check_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','timeout','unsupported','unexamined')),
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    source_event_id TEXT REFERENCES run_events(id) ON DELETE RESTRICT,
                    UNIQUE(run_id, seq)
                );
                CREATE INDEX IF NOT EXISTS idx_runs_evidence_created ON runs(evidence_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runs_case_evidence_created ON runs(case_id, evidence_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_run_events_run_seq ON run_events(run_id, seq);
                CREATE TRIGGER IF NOT EXISTS immutable_completed_run_event_update
                BEFORE UPDATE ON run_events WHEN OLD.status = 'completed'
                BEGIN SELECT RAISE(ABORT, 'completed run events are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_completed_run_event_delete
                BEFORE DELETE ON run_events WHEN OLD.status = 'completed'
                BEGIN SELECT RAISE(ABORT, 'completed run events are immutable'); END;
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (3, ?)",
                (utc_now(),),
            )

    def backfill_review_findings(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            missing = connection.execute(
                """SELECT r.case_id, e.timestamp, f.value AS finding_json
                   FROM run_events e JOIN runs r ON r.id = e.run_id
                   JOIN json_each(e.payload_json, '$.findings') f
                   WHERE json_type(f.value, '$.finding_id') = 'text'
                     AND NOT EXISTS (
                         SELECT 1 FROM findings registered
                         WHERE registered.finding_id = json_extract(f.value, '$.finding_id')
                     )
                   ORDER BY e.timestamp, e.seq"""
            )
            for row in missing:
                CaseRepository.register_finding_in_transaction(
                    connection, json.loads(row["finding_json"]), row["case_id"], row["timestamp"],
                )

    def resolve_evidence(self, evidence_id: str, case_id: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            if case_id:
                rows = connection.execute(
                    "SELECT * FROM case_evidence WHERE case_id = ? AND evidence_id = ?",
                    (case_id, evidence_id),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM case_evidence WHERE evidence_id = ?", (evidence_id,)
                ).fetchall()
        if not rows:
            raise EvidenceNotFoundError(evidence_id)
        if len(rows) > 1:
            raise AmbiguousEvidenceError(evidence_id)
        return dict(rows[0])

    @staticmethod
    def default_checks(kind: str) -> list[str]:
        if kind == "image":
            return ["image_model", "face_forgery", "file_inspection"]
        if kind == "audio":
            return ["audio_model", "file_inspection"]
        return ["video_frame_analysis"]

    def create_run(
        self,
        evidence_id: str,
        case_id: str | None = None,
        retry_of_run_id: str | None = None,
        retry_checks: list[str] | None = None,
        input_path: str | None = None,
    ) -> dict[str, Any]:
        evidence = self.resolve_evidence(evidence_id, case_id)
        now = utc_now()
        run_id = "RUN-" + uuid.uuid4().hex
        carried: list[sqlite3.Row] = []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = 1
            checks = self.default_checks(evidence["media_type"])
            if retry_of_run_id:
                parent = connection.execute("SELECT * FROM runs WHERE id = ?", (retry_of_run_id,)).fetchone()
                if not parent or parent["case_id"] != evidence["case_id"] or parent["evidence_id"] != evidence_id:
                    raise InvalidRetryError("retry parent does not belong to this evidence")
                attempt = int(parent["attempt"]) + 1
                input_path = input_path or parent["input_path"]
                latest = self._latest_events(connection, retry_of_run_id)
                carried = [event for event in latest.values() if event["status"] == "completed"]
                eligible = [name for name, event in latest.items() if event["status"] != "completed"]
                if retry_checks is not None:
                    unknown = set(retry_checks) - set(eligible)
                    if unknown:
                        raise InvalidRetryError("retry checks must be failed or unfinished: " + ", ".join(sorted(unknown)))
                    eligible = list(dict.fromkeys(retry_checks))
                checks = eligible
                if not checks:
                    raise InvalidRetryError("the parent run has no failed or unfinished checks")
            connection.execute(
                """INSERT INTO runs(id, case_id, evidence_id, status, created_at, retry_of_run_id,
                       attempt, kind, requested_checks_json, input_path)
                   VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)""",
                (run_id, evidence["case_id"], evidence_id, now, retry_of_run_id, attempt,
                 evidence["media_type"], json.dumps(checks), input_path),
            )
            seq = 0
            for event in carried:
                seq += 1
                connection.execute(
                    """INSERT INTO run_events(id, run_id, seq, timestamp, check_name, event_type,
                           status, payload_json, source_event_id) VALUES (?, ?, ?, ?, ?, 'carried_forward',
                           'completed', ?, ?)""",
                    ("EVT-" + uuid.uuid4().hex, run_id, seq, now, event["check_name"],
                     json.dumps({"source_run_id": retry_of_run_id}), event["id"]),
                )
            for check in checks:
                seq += 1
                connection.execute(
                    """INSERT INTO run_events(id, run_id, seq, timestamp, check_name, event_type,
                           status, payload_json) VALUES (?, ?, ?, ?, ?, 'check.queued', 'queued', '{}')""",
                    ("EVT-" + uuid.uuid4().hex, run_id, seq, now, check),
                )
            connection.commit()
        return self.get_run(run_id)

    @staticmethod
    def _latest_events(connection: sqlite3.Connection, run_id: str) -> dict[str, sqlite3.Row]:
        rows = connection.execute(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY seq", (run_id,)
        ).fetchall()
        latest: dict[str, sqlite3.Row] = {}
        for row in rows:
            latest[row["check_name"]] = row
        return latest

    def append_event(self, run_id: str, check_name: str, event_type: str, status: str,
                     payload: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not run:
                raise RunNotFoundError(run_id)
            seq = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM run_events WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO run_events(id, run_id, seq, timestamp, check_name, event_type,
                       status, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("EVT-" + uuid.uuid4().hex, run_id, seq, now, check_name, event_type,
                 status, json.dumps(payload or {}, separators=(",", ":"), sort_keys=True)),
            )
            for finding in (payload or {}).get("findings", []):
                CaseRepository.register_finding_in_transaction(connection, finding, run["case_id"], now)
            latest = self._latest_events(connection, run_id)
            aggregate = aggregate_run_status(event["status"] for event in latest.values())
            terminal = all(event["status"] in TERMINAL_CHECK_STATUSES for event in latest.values())
            error = None
            if terminal:
                errors = [json.loads(event["payload_json"]) for event in latest.values()
                          if event["status"] in {"failed", "timeout", "unsupported"}]
                error = json.dumps(errors[-1]) if errors else None
            connection.execute(
                """UPDATE runs SET status = ?, started_at = CASE WHEN ? = 'running' THEN COALESCE(started_at, ?) ELSE started_at END,
                       finished_at = CASE WHEN ? THEN COALESCE(finished_at, ?) ELSE NULL END,
                       error_json = ? WHERE id = ?""",
                (aggregate, aggregate, now, terminal, now, error, run_id),
            )
            if aggregate == "running" and run["status"] != "running":
                CaseRepository._insert_event(
                    connection, run["case_id"], "run.started", "Analysis service", now,
                    {"status": "running"}, evidence_id=run["evidence_id"], run_id=run_id,
                    summary=f"Run {run_id} started", event_id=f"RUN-ACTIVITY-START-{run_id}",
                )
            terminal_type = {"completed": "run.completed", "partial": "run.partial",
                             "failed": "run.failed"}.get(aggregate)
            if terminal and terminal_type and run["status"] != aggregate:
                CaseRepository._insert_event(
                    connection, run["case_id"], terminal_type, "Analysis service", now,
                    {"status": aggregate}, evidence_id=run["evidence_id"], run_id=run_id,
                    summary=f"Run {run_id} {aggregate}", event_id=f"RUN-ACTIVITY-END-{run_id}",
                )
            connection.commit()
        return self.get_run(run_id)

    def _event_dict(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(row["payload_json"])
        if row["source_event_id"]:
            source = connection.execute("SELECT * FROM run_events WHERE id = ?", (row["source_event_id"],)).fetchone()
            if source:
                payload = {**self._event_dict(connection, source)["payload"], **payload,
                           "carried_from_event_id": source["id"], "carried_from_run_id": source["run_id"]}
        return {"id": row["id"], "seq": row["seq"], "timestamp": row["timestamp"],
                "check": row["check_name"], "event_type": row["event_type"],
                "status": row["status"], "payload": payload,
                "source_event_id": row["source_event_id"]}

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                raise RunNotFoundError(run_id)
            events = [self._event_dict(connection, event) for event in connection.execute(
                "SELECT * FROM run_events WHERE run_id = ? ORDER BY seq", (run_id,)
            )]
            children = [item[0] for item in connection.execute(
                "SELECT id FROM runs WHERE retry_of_run_id = ? ORDER BY created_at", (run_id,)
            )]
        findings = [finding for event in events for finding in event["payload"].get("findings", [])]
        coverage = next((event["payload"].get("coverage") for event in reversed(events)
                         if event["payload"].get("coverage") is not None), None)
        errors = [event["payload"].get("error") for event in events if event["payload"].get("error")]
        return {"schema_version": "1.1", "run_id": row["id"], "case_id": row["case_id"],
                "evidence_id": row["evidence_id"], "modality": row["kind"],
                "execution_status": row["status"], "requested_at": row["created_at"],
                "started_at": row["started_at"], "completed_at": row["finished_at"],
                "retry_of": row["retry_of_run_id"], "retry_children": children,
                "attempt": row["attempt"], "requested_checks": json.loads(row["requested_checks_json"]),
                "configuration": {"name": "persistent analysis", "version": "run-store-1.0"},
                "configuration_version": "run-store-1.0", "findings": findings,
                "coverage": coverage, "artifacts": [], "errors": errors, "fixture": False,
                "origin": "server", "events": events, "input_available": bool(row["input_path"])}

    def list_runs(self, evidence_id: str, case_id: str | None = None) -> list[dict[str, Any]]:
        evidence = self.resolve_evidence(evidence_id, case_id)
        with self._connect() as connection:
            ids = [row[0] for row in connection.execute(
                "SELECT id FROM runs WHERE case_id = ? AND evidence_id = ? ORDER BY created_at DESC, id DESC",
                (evidence["case_id"], evidence_id),
            )]
        return [self.get_run(run_id) for run_id in ids]

    def input_path(self, run_id: str) -> Path | None:
        with self._connect() as connection:
            row = connection.execute("SELECT input_path FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise RunNotFoundError(run_id)
        return Path(row[0]) if row[0] else None

    def recover_stale_runs(self) -> int:
        with self._connect() as connection:
            ids = [row[0] for row in connection.execute(
                "SELECT id FROM runs WHERE status IN ('queued','running')"
            )]
        for run_id in ids:
            run = self.get_run(run_id)
            active = {event["check"]: event["status"] for event in run["events"]}
            for check, status in active.items():
                if status in {"queued", "running"}:
                    self.append_event(run_id, check, "check.interrupted", "failed", {
                        "error": {"code": "SERVER_RESTART", "message": "The server restarted before this check finished.", "retryable": True}
                    })
        return len(ids)
