import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_database_path() -> Path:
    configured = os.getenv("PRATYAKSH_DB_PATH")
    return Path(configured) if configured else Path(__file__).resolve().parents[1] / "data" / "pratyaksh.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CaseNotFoundError(LookupError):
    pass


class DuplicateEvidenceError(ValueError):
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

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                return connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 1
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
                "created_by": actor,
                "created_by_verified": False,
            }
            connection.execute(
                "INSERT INTO cases(id, title, description, status, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                (case_id, title, description or "", "Open", created_at, actor),
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

    def list_cases(self, q: str | None, status: str | None, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
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
            rows = connection.execute(
                f"SELECT * FROM cases{where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                [*parameters, limit, offset],
            ).fetchall()
        return [self._case_dict(row) for row in rows], total

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
            "hash_source": row["hash_source"],
            "registered_at": row["registered_at"],
            "registered_by": row["registered_by"],
            "registered_by_verified": False,
            "preserved": False,
            "preserved_evidence_id": row["preserved_evidence_id"],
            "duplicate_hash_of": duplicates or [],
        }

    def register_evidence(self, case_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any]:
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
                        hash_source, preserved_evidence_id, registered_at, registered_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'client_declared', NULL, ?, ?)""",
                    (
                        case_id,
                        evidence_id,
                        payload["filename"],
                        payload["media_type"],
                        payload["role"],
                        payload["size_bytes"],
                        payload["sha256"],
                        registered_at,
                        actor,
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
                {"evidence_id": evidence_id, "sha256": payload["sha256"], "preserved": False},
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

    def list_events(self, case_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM case_events WHERE case_id = ? ORDER BY at, id", (case_id,)
            ).fetchall()
        return [{**dict(row), "detail": json.loads(row["detail"])} for row in rows]

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        case_id: str,
        event_type: str,
        actor: str,
        at: str,
        detail: dict[str, Any],
    ) -> None:
        connection.execute(
            "INSERT INTO case_events(id, case_id, event_type, actor, at, detail) VALUES (?, ?, ?, ?, ?, ?)",
            ("EVT-" + uuid.uuid4().hex, case_id, event_type, actor, at, json.dumps(detail, sort_keys=True)),
        )
