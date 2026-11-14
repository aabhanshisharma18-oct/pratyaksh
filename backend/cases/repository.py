import json
import hashlib
import base64
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CASE_EVENT_TYPES = {
    "case.created", "evidence.registered", "run.started", "run.completed",
    "run.failed", "run.partial", "note.added", "finding.created",
}


def default_database_path() -> Path:
    configured = os.getenv("PRATYAKSH_DB_PATH")
    return Path(configured) if configured else Path(__file__).resolve().parents[1] / "data" / "pratyaksh.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CaseNotFoundError(LookupError):
    pass


class DuplicateEvidenceError(ValueError):
    pass


class FindingNotFoundError(LookupError):
    pass


class FindingConflictError(ValueError):
    pass


class _ClosingConnection(sqlite3.Connection):
    """Commit or roll back like sqlite3.Connection, then release Windows locks."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class CaseRepository:
    """SQLite-backed case inventory store with one connection per operation."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = Path(database_path) if database_path else default_database_path()
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
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS case_sequences (
                    year INTEGER PRIMARY KEY,
                    next_value INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence_sequences (
                    case_id TEXT PRIMARY KEY REFERENCES cases(id) ON DELETE RESTRICT,
                    next_value INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS case_evidence (
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
                    evidence_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    media_type TEXT NOT NULL CHECK(media_type IN ('image', 'audio', 'video')),
                    role TEXT NOT NULL CHECK(role IN ('Evidence', 'Reference', 'Control')),
                    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                    sha256 TEXT NOT NULL,
                    hash_source TEXT NOT NULL CHECK(hash_source = 'client_declared'),
                    preserved_evidence_id TEXT,
                    registered_at TEXT NOT NULL,
                    registered_by TEXT NOT NULL,
                    PRIMARY KEY (case_id, evidence_id)
                );
                CREATE TABLE IF NOT EXISTS case_events (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
                    event_type TEXT NOT NULL CHECK(event_type IN ('case.created', 'evidence.registered')),
                    actor TEXT NOT NULL,
                    at TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_case_evidence_hash ON case_evidence(case_id, sha256);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (1, ?)",
                (utc_now(),),
            )
            current_version = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            if current_version < 2:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS findings (
                        finding_id TEXT PRIMARY KEY,
                        evidence_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        case_id TEXT REFERENCES cases(id) ON DELETE RESTRICT,
                        recorded_at TEXT NOT NULL,
                        finding_json TEXT NOT NULL,
                        finding_sha256 TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS finding_notes (
                        note_id TEXT PRIMARY KEY,
                        finding_id TEXT NOT NULL REFERENCES findings(finding_id) ON DELETE RESTRICT,
                        finding_sha256 TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('reviewed', 'questioned')),
                        text TEXT NOT NULL,
                        author TEXT NOT NULL,
                        author_verified INTEGER NOT NULL DEFAULT 0 CHECK(author_verified = 0),
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS finding_events (
                        id TEXT PRIMARY KEY,
                        case_id TEXT REFERENCES cases(id) ON DELETE RESTRICT,
                        finding_id TEXT NOT NULL REFERENCES findings(finding_id) ON DELETE RESTRICT,
                        event_type TEXT NOT NULL CHECK(event_type = 'finding.note_added'),
                        actor TEXT NOT NULL,
                        at TEXT NOT NULL,
                        detail TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_findings_evidence ON findings(evidence_id, recorded_at);
                    CREATE INDEX IF NOT EXISTS idx_finding_notes_finding ON finding_notes(finding_id, created_at, note_id);
                    """
                )
                connection.execute(
                    "INSERT INTO schema_version(version, applied_at) VALUES (2, ?)",
                    (utc_now(),),
                )
            current_version = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            if current_version < 4:
                case_columns = {row["name"] for row in connection.execute("PRAGMA table_info(cases)")}
                if "last_activity_at" not in case_columns:
                    connection.execute("ALTER TABLE cases ADD COLUMN last_activity_at TEXT")
                connection.execute("UPDATE cases SET last_activity_at = created_at WHERE last_activity_at IS NULL")
                event_columns = {row["name"] for row in connection.execute("PRAGMA table_info(case_events)")}
                if "created_at" not in event_columns:
                    connection.executescript(
                        """
                        ALTER TABLE case_events RENAME TO case_events_legacy;
                        CREATE TABLE case_events (
                            id TEXT PRIMARY KEY,
                            case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
                            event_type TEXT NOT NULL CHECK(event_type IN (
                                'case.created','evidence.registered','run.started','run.completed',
                                'run.failed','run.partial','note.added','finding.created'
                            )),
                            evidence_id TEXT,
                            run_id TEXT,
                            actor TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            summary TEXT NOT NULL,
                            payload_json TEXT NOT NULL
                        );
                        INSERT INTO case_events(
                            id, case_id, event_type, evidence_id, run_id, actor, created_at, summary, payload_json
                        )
                        SELECT id, case_id, event_type,
                               CASE WHEN event_type = 'evidence.registered' THEN json_extract(detail, '$.evidence_id') END,
                               NULL, actor, at,
                               CASE WHEN event_type = 'case.created' THEN 'Case created' ELSE 'Evidence registered' END,
                               detail
                        FROM case_events_legacy;
                        DROP TABLE case_events_legacy;
                        """
                    )
                connection.executescript(
                    """
                    CREATE INDEX IF NOT EXISTS idx_case_events_case_created
                        ON case_events(case_id, created_at DESC, id DESC);
                    CREATE INDEX IF NOT EXISTS idx_case_events_subjects
                        ON case_events(case_id, evidence_id, run_id);
                    """
                )
                self._backfill_events(connection)
                connection.execute(
                    "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (4, ?)", (utc_now(),)
                )

            evidence_columns = {row["name"] for row in connection.execute("PRAGMA table_info(case_evidence)")}
            if "receipt_json" not in evidence_columns:
                connection.execute("ALTER TABLE case_evidence ADD COLUMN receipt_json TEXT")
            connection.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (5, ?)", (utc_now(),)
            )

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                return connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] >= 2
        except sqlite3.Error:
            return False

    @staticmethod
    def _case_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "created_at": row["created_at"],
            "last_activity_at": row["last_activity_at"] or row["created_at"],
            "created_by": row["created_by"],
            "created_by_verified": False,
        }

    def create_case(self, title: str, description: str | None, actor: str) -> dict[str, Any]:
        year = datetime.now(timezone.utc).year
        created_at = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT next_value FROM case_sequences WHERE year = ?", (year,)).fetchone()
            sequence = row[0] if row else 1
            if row:
                connection.execute("UPDATE case_sequences SET next_value = ? WHERE year = ?", (sequence + 1, year))
            else:
                connection.execute("INSERT INTO case_sequences(year, next_value) VALUES (?, ?)", (year, 2))
            case_id = f"CASE-{year}-{sequence:06d}"
            record = {
                "id": case_id,
                "title": title,
                "description": description or "",
                "status": "Open",
                "created_at": created_at,
                "last_activity_at": created_at,
                "created_by": actor,
                "created_by_verified": False,
            }
            connection.execute(
                "INSERT INTO cases(id, title, description, status, created_at, created_by, last_activity_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (case_id, title, description or "", "Open", created_at, actor, created_at),
            )
            self._insert_event(connection, case_id, "case.created", actor, created_at, {"title": title})
            connection.commit()
        return record

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            if not row:
                return None
            counts = {"image": 0, "audio": 0, "video": 0}
            for count_row in connection.execute(
                "SELECT media_type, COUNT(*) AS count FROM case_evidence WHERE case_id = ? GROUP BY media_type",
                (case_id,),
            ):
                counts[count_row["media_type"]] = count_row["count"]
            record = self._case_dict(row)
            record.update(evidence_count=sum(counts.values()), evidence_by_media_type=counts)
            return record

    def list_cases(self, q: str | None, status: str | None, limit: int, offset: int,
                   sort_by: str = "last_activity_at", order: str = "desc") -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if q:
            clauses.append("(LOWER(id) LIKE ? OR LOWER(title) LIKE ?)")
            needle = f"%{q.lower()}%"
            parameters.extend([needle, needle])
        if status:
            clauses.append("LOWER(status) = LOWER(?)")
            parameters.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM cases{where}", parameters).fetchone()[0]
            direction = "ASC" if order == "asc" else "DESC"
            sort_column = {"last_activity_at": "c.last_activity_at", "created_at": "c.created_at", "title": "c.title"}[sort_by]
            rows = connection.execute(
                f"""SELECT c.*, COUNT(e.evidence_id) AS evidence_count FROM cases c
                    LEFT JOIN case_evidence e ON e.case_id = c.id{where.replace('cases.', 'c.')}
                    GROUP BY c.id ORDER BY {sort_column} {direction}, c.id {direction} LIMIT ? OFFSET ?""",
                [*parameters, limit, offset],
            ).fetchall()
        records = []
        for row in rows:
            record = self._case_dict(row)
            record["evidence_count"] = row["evidence_count"]
            records.append(record)
        return records, total

    @staticmethod
    def _evidence_dict(row: sqlite3.Row, duplicates: list[str] | None = None) -> dict[str, Any]:
        return {
            "case_id": row["case_id"],
            "evidence_id": row["evidence_id"],
            "filename": row["filename"],
            "media_type": row["media_type"],
            "role": row["role"],
            "size_bytes": row["size_bytes"],
            "sha256": row["sha256"],
            "hash_source": "server_computed" if row["preserved_evidence_id"] else row["hash_source"],
            "registered_at": row["registered_at"],
            "registered_by": row["registered_by"],
            "registered_by_verified": False,
            "preserved": bool(row["preserved_evidence_id"]),
            "preserved_evidence_id": row["preserved_evidence_id"],
            "duplicate_hash_of": duplicates or [],
            "receipt": json.loads(row["receipt_json"]) if row["receipt_json"] else None,
        }

    def register_evidence(self, case_id: str, payload: dict[str, Any], actor: str, *, preserved_hash: str | None = None, receipt: dict[str, str] | None = None) -> dict[str, Any]:
        registered_at = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone():
                raise CaseNotFoundError(case_id)
            evidence_id = payload.get("evidence_id")
            if evidence_id is None:
                sequence_row = connection.execute(
                    "SELECT next_value FROM evidence_sequences WHERE case_id = ?", (case_id,)
                ).fetchone()
                sequence = sequence_row[0] if sequence_row else 1
                evidence_id = f"EVID-{sequence}"
                if sequence_row:
                    connection.execute(
                        "UPDATE evidence_sequences SET next_value = ? WHERE case_id = ?", (sequence + 1, case_id)
                    )
                else:
                    connection.execute(
                        "INSERT INTO evidence_sequences(case_id, next_value) VALUES (?, ?)", (case_id, 2)
                    )
            duplicate_rows = connection.execute(
                "SELECT evidence_id FROM case_evidence WHERE case_id = ? AND sha256 = ? ORDER BY evidence_id",
                (case_id, payload["sha256"]),
            ).fetchall()
            try:
                connection.execute(
                    """INSERT INTO case_evidence(
                        case_id, evidence_id, filename, media_type, role, size_bytes, sha256,
                        hash_source, preserved_evidence_id, registered_at, registered_by, receipt_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'client_declared', ?, ?, ?, ?)""",
                    (
                        case_id,
                        evidence_id,
                        payload["filename"],
                        payload["media_type"],
                        payload["role"],
                        payload["size_bytes"],
                        payload["sha256"],
                        preserved_hash,
                        registered_at,
                        actor,
                        json.dumps(receipt) if receipt else None,
                    ),
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE constraint failed" in str(error):
                    raise DuplicateEvidenceError(evidence_id) from error
                raise
            self._insert_event(
                connection,
                case_id,
                "evidence.registered",
                actor,
                registered_at,
                {"evidence_id": evidence_id, "sha256": payload["sha256"], "preserved": bool(preserved_hash),
                 **({"receipt_recorded": True} if receipt else {})},
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM case_evidence WHERE case_id = ? AND evidence_id = ?", (case_id, evidence_id)
            ).fetchone()
        return self._evidence_dict(row, [item["evidence_id"] for item in duplicate_rows])

    def list_evidence(
        self, case_id: str, role: str | None = None, media_type: str | None = None
    ) -> list[dict[str, Any]]:
        clauses = ["case_id = ?"]
        parameters: list[Any] = [case_id]
        if role:
            clauses.append("role = ?")
            parameters.append(role)
        if media_type:
            clauses.append("media_type = ?")
            parameters.append(media_type)
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone():
                raise CaseNotFoundError(case_id)
            rows = connection.execute(
                f"SELECT * FROM case_evidence WHERE {' AND '.join(clauses)} ORDER BY registered_at, evidence_id",
                parameters,
            ).fetchall()
        return [self._evidence_dict(row) for row in rows]

    @staticmethod
    def _event_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "type": row["event_type"], "case_id": row["case_id"],
            "evidence_id": row["evidence_id"], "run_id": row["run_id"], "actor": row["actor"],
            "created_at": row["created_at"], "summary": row["summary"],
            "payload": json.loads(row["payload_json"]),
        }

    def list_events(self, case_id: str) -> list[dict[str, Any]]:
        """Compatibility helper used by repository tests; public API uses cursor pagination."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM case_events WHERE case_id = ? ORDER BY created_at, id", (case_id,)
            ).fetchall()
        return self._event_dict_legacy(rows)

    @staticmethod
    def _event_dict_legacy(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [{"id": row["id"], "case_id": row["case_id"], "event_type": row["event_type"],
                 "actor": row["actor"], "at": row["created_at"],
                 "detail": json.loads(row["payload_json"])} for row in rows]

    @staticmethod
    def _encode_cursor(created_at: str, event_id: str) -> str:
        raw = json.dumps([created_at, event_id], separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[str, str]:
        try:
            raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
            value = json.loads(raw)
            if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, str) for item in value):
                raise ValueError
            datetime.fromisoformat(value[0].replace("Z", "+00:00"))
            return value[0], value[1]
        except Exception as error:
            raise ValueError("Invalid event cursor") from error

    def query_events(self, case_id: str, event_types: list[str] | None = None,
                     evidence_id: str | None = None, run_id: str | None = None,
                     actor: str | None = None, from_at: str | None = None,
                     to_at: str | None = None, limit: int = 25,
                     cursor: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
        clauses = ["case_id = ?"]
        parameters: list[Any] = [case_id]
        if event_types:
            unknown = set(event_types) - CASE_EVENT_TYPES
            if unknown:
                raise ValueError("Unknown event type: " + ", ".join(sorted(unknown)))
            clauses.append("event_type IN (" + ",".join("?" for _ in event_types) + ")")
            parameters.extend(event_types)
        for column, value in (("evidence_id", evidence_id), ("run_id", run_id), ("actor", actor)):
            if value:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        if from_at:
            clauses.append("created_at >= ?")
            parameters.append(from_at)
        if to_at:
            clauses.append("created_at <= ?")
            parameters.append(to_at)
        if cursor:
            cursor_at, cursor_id = self._decode_cursor(cursor)
            clauses.append("(created_at < ? OR (created_at = ? AND id < ?))")
            parameters.extend([cursor_at, cursor_at, cursor_id])
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone():
                raise CaseNotFoundError(case_id)
            rows = connection.execute(
                f"SELECT * FROM case_events WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC, id DESC LIMIT ?", [*parameters, limit + 1],
            ).fetchall()
        page = rows[:limit]
        next_cursor = self._encode_cursor(page[-1]["created_at"], page[-1]["id"]) if len(rows) > limit else None
        return [self._event_dict(row) for row in page], next_cursor

    @staticmethod
    def _canonical_finding(finding: dict[str, Any]) -> tuple[str, str]:
        canonical = json.dumps(finding, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def register_finding(self, finding: dict[str, Any], case_id: str | None) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self.register_finding_in_transaction(connection, finding, case_id, utc_now())

    @classmethod
    def register_finding_in_transaction(
        cls, connection: sqlite3.Connection, finding: dict[str, Any],
        case_id: str | None, recorded_at: str,
    ) -> dict[str, Any]:
        required = ("finding_id", "evidence_id", "run_id")
        if any(not isinstance(finding.get(field), str) or not finding[field] for field in required):
            raise ValueError("finding_id, evidence_id and run_id are required")
        canonical, digest = cls._canonical_finding(finding)
        if case_id:
            belongs = connection.execute(
                "SELECT 1 FROM case_evidence WHERE case_id = ? AND evidence_id = ?",
                (case_id, finding["evidence_id"]),
            ).fetchone()
            if not belongs:
                raise CaseNotFoundError(case_id)
        existing = connection.execute(
            "SELECT * FROM findings WHERE finding_id = ?", (finding["finding_id"],)
        ).fetchone()
        if existing:
            if existing["finding_sha256"] != digest:
                raise FindingConflictError(finding["finding_id"])
            return cls._finding_dict(existing)
        connection.execute(
            """INSERT INTO findings(
                finding_id, evidence_id, run_id, case_id, recorded_at, finding_json, finding_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                finding["finding_id"], finding["evidence_id"], finding["run_id"], case_id,
                recorded_at, canonical, digest,
            ),
        )
        if case_id:
            cls._insert_event(
                connection, case_id, "finding.created", "Analysis service", recorded_at,
                {"finding_id": finding["finding_id"], "category": finding.get("category")},
                evidence_id=finding["evidence_id"], run_id=finding["run_id"],
                summary=f"Finding {finding['finding_id']} recorded",
            )
        row = connection.execute(
            "SELECT * FROM findings WHERE finding_id = ?", (finding["finding_id"],)
        ).fetchone()
        return cls._finding_dict(row)

    def list_findings(self, case_id: str | None = None, evidence_id: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if case_id:
            clauses.append("case_id = ?")
            parameters.append(case_id)
        if evidence_id:
            clauses.append("evidence_id = ?")
            parameters.append(evidence_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            if case_id and not connection.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone():
                raise CaseNotFoundError(case_id)
            rows = connection.execute(
                f"SELECT * FROM findings{where} ORDER BY recorded_at, finding_id", parameters
            ).fetchall()
        return [self._finding_dict(row) for row in rows]

    @staticmethod
    def _finding_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "finding_id": row["finding_id"], "evidence_id": row["evidence_id"],
            "run_id": row["run_id"], "case_id": row["case_id"],
            "recorded_at": row["recorded_at"], "finding_sha256": row["finding_sha256"],
            "finding": json.loads(row["finding_json"]),
        }

    def add_finding_note(self, finding_id: str, status: str, text: str, author: str) -> dict[str, Any]:
        created_at = utc_now()
        note_id = "NOTE-" + uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            finding = connection.execute(
                "SELECT finding_sha256, case_id FROM findings WHERE finding_id = ?", (finding_id,)
            ).fetchone()
            if not finding:
                raise FindingNotFoundError(finding_id)
            connection.execute(
                """INSERT INTO finding_notes(
                    note_id, finding_id, finding_sha256, status, text, author, author_verified, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (note_id, finding_id, finding["finding_sha256"], status, text, author, created_at),
            )
            connection.execute(
                """INSERT INTO finding_events(
                    id, case_id, finding_id, event_type, actor, at, detail
                ) VALUES (?, ?, ?, 'finding.note_added', ?, ?, ?)""",
                (
                    "FEVT-" + uuid.uuid4().hex, finding["case_id"], finding_id, author, created_at,
                    json.dumps({"note_id": note_id, "status": status}, sort_keys=True),
                ),
            )
            if finding["case_id"]:
                subject = connection.execute(
                    "SELECT evidence_id, run_id FROM findings WHERE finding_id = ?", (finding_id,)
                ).fetchone()
                self._insert_event(
                    connection, finding["case_id"], "note.added", author, created_at,
                    {"note_id": note_id, "finding_id": finding_id, "status": status,
                     "excerpt": text[:120]}, evidence_id=subject["evidence_id"],
                    run_id=subject["run_id"], summary=f"Reviewer note added to {finding_id}",
                )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM finding_notes WHERE note_id = ?", (note_id,)
            ).fetchone()
        return self._note_dict(row)

    def list_finding_notes(self, finding_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM findings WHERE finding_id = ?", (finding_id,)).fetchone():
                raise FindingNotFoundError(finding_id)
            rows = connection.execute(
                "SELECT * FROM finding_notes WHERE finding_id = ? ORDER BY created_at, note_id",
                (finding_id,),
            ).fetchall()
        return [self._note_dict(row) for row in rows]

    @staticmethod
    def _note_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "note_id": row["note_id"], "finding_id": row["finding_id"],
            "finding_sha256": row["finding_sha256"], "status": row["status"],
            "text": row["text"], "author": row["author"],
            "author_verified": False, "created_at": row["created_at"],
        }

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        case_id: str,
        event_type: str,
        actor: str,
        at: str,
        detail: dict[str, Any],
        *, evidence_id: str | None = None, run_id: str | None = None,
        summary: str | None = None, event_id: str | None = None,
    ) -> None:
        if event_type not in CASE_EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type}")
        evidence_id = evidence_id or detail.get("evidence_id")
        run_id = run_id or detail.get("run_id")
        summaries = {"case.created": "Case created", "evidence.registered": "Evidence registered",
                     "finding.created": "Finding recorded", "note.added": "Reviewer note added",
                     "run.started": "Analysis run started", "run.completed": "Analysis run completed",
                     "run.failed": "Analysis run failed", "run.partial": "Analysis run completed partially"}
        connection.execute(
            """INSERT OR IGNORE INTO case_events(
                   id, case_id, event_type, evidence_id, run_id, actor, created_at, summary, payload_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id or "EVT-" + uuid.uuid4().hex, case_id, event_type, evidence_id, run_id,
             actor, at, summary or summaries[event_type], json.dumps(detail, sort_keys=True)),
        )
        connection.execute(
            """UPDATE cases SET last_activity_at = CASE
                   WHEN last_activity_at IS NULL OR last_activity_at < ? THEN ? ELSE last_activity_at END
               WHERE id = ?""", (at, at, case_id),
        )

    def _backfill_events(self, connection: sqlite3.Connection) -> None:
        for row in connection.execute("SELECT id, title, created_at, created_by FROM cases"):
            self._insert_event(connection, row["id"], "case.created", row["created_by"], row["created_at"],
                               {"title": row["title"]}, event_id="BF-CASE-" + row["id"])
        for row in connection.execute("SELECT * FROM case_evidence"):
            self._insert_event(connection, row["case_id"], "evidence.registered", row["registered_by"],
                               row["registered_at"], {"evidence_id": row["evidence_id"],
                               "sha256": row["sha256"], "preserved": bool(row["preserved_evidence_id"])},
                               evidence_id=row["evidence_id"], summary=f"Evidence {row['evidence_id']} registered",
                               event_id=f"BF-EVIDENCE-{row['case_id']}-{row['evidence_id']}")
        for row in connection.execute("SELECT finding_id, case_id, evidence_id, run_id, recorded_at, finding_json FROM findings WHERE case_id IS NOT NULL"):
            finding = json.loads(row["finding_json"])
            self._insert_event(connection, row["case_id"], "finding.created", "Analysis service",
                               row["recorded_at"], {"finding_id": row["finding_id"],
                               "category": finding.get("category")}, evidence_id=row["evidence_id"],
                               run_id=row["run_id"], summary=f"Finding {row['finding_id']} recorded",
                               event_id="BF-FINDING-" + row["finding_id"])
        for row in connection.execute("""SELECT n.*, f.case_id, f.evidence_id, f.run_id
                                          FROM finding_notes n JOIN findings f ON f.finding_id=n.finding_id
                                          WHERE f.case_id IS NOT NULL"""):
            self._insert_event(connection, row["case_id"], "note.added", row["author"], row["created_at"],
                               {"note_id": row["note_id"], "finding_id": row["finding_id"],
                                "status": row["status"], "excerpt": row["text"][:120]},
                               evidence_id=row["evidence_id"], run_id=row["run_id"],
                               summary=f"Reviewer note added to {row['finding_id']}",
                               event_id="BF-NOTE-" + row["note_id"])
        has_runs = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'").fetchone()
        if has_runs:
            for row in connection.execute("SELECT * FROM runs"):
                if row["started_at"]:
                    self._insert_event(connection, row["case_id"], "run.started", "Analysis service",
                                       row["started_at"], {"status": "running"}, evidence_id=row["evidence_id"],
                                       run_id=row["id"], summary=f"Run {row['id']} started",
                                       event_id="BF-RUN-START-" + row["id"])
                terminal_type = {"completed": "run.completed", "partial": "run.partial",
                                 "failed": "run.failed"}.get(row["status"])
                if terminal_type and row["finished_at"]:
                    self._insert_event(connection, row["case_id"], terminal_type, "Analysis service",
                                       row["finished_at"], {"status": row["status"]}, evidence_id=row["evidence_id"],
                                       run_id=row["id"], summary=f"Run {row['id']} {row['status']}",
                                       event_id="BF-RUN-END-" + row["id"])
