from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase): pass


class CaseCounter(Base):
    __tablename__ = "d2_case_counters"
    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Evidence(Base):
    __tablename__ = "d2_evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(String, index=True)
    original_filename: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text, unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    receipt_context: Mapped[str] = mapped_column(Text, default="")
    uploader_identity: Mapped[str] = mapped_column(Text)
    integrity_status: Mapped[str] = mapped_column(String, default="Not Yet Verified")
    derivatives: Mapped[list["Derivative"]] = relationship(back_populates="evidence")


class Derivative(Base):
    __tablename__ = "d2_derivatives"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("d2_evidence.id"), index=True)
    kind: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(Text, unique=True)
    transformation: Mapped[str] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSON)
    tool_versions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sha256: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[Evidence] = relationship(back_populates="derivatives")


class AuditEntry(Base):
    __tablename__ = "d2_audit_entries"
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(Text)
    action_type: Mapped[str] = mapped_column(String, index=True)
    evidence_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    result: Mapped[str] = mapped_column(String)
    parameters: Mapped[dict] = mapped_column(JSON)
    previous_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


class MetadataSnapshot(Base):
    __tablename__ = "d2_metadata_snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("d2_evidence.id"), index=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    raw: Mapped[dict] = mapped_column(JSON)
    normalized: Mapped[dict] = mapped_column(JSON)
    tool_versions: Mapped[dict] = mapped_column(JSON)


class AnalysisRun(Base):
    __tablename__ = "d2_analysis_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("d2_evidence.id"), index=True)
    method: Mapped[str] = mapped_column(String)
    method_version: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    format_support: Mapped[str] = mapped_column(String)
    decoding: Mapped[str] = mapped_column(String)
    analysis: Mapped[str] = mapped_column(String)
    parameters: Mapped[dict] = mapped_column(JSON)
    findings: Mapped[dict] = mapped_column(JSON)
    interpretation: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list] = mapped_column(JSON)
    artifacts: Mapped[list] = mapped_column(JSON)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class D2Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", self._configure_sqlite)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER IF NOT EXISTS d2_audit_no_update BEFORE UPDATE ON d2_audit_entries BEGIN SELECT RAISE(ABORT, 'audit entries are append-only'); END"))
            connection.execute(text("CREATE TRIGGER IF NOT EXISTS d2_audit_no_delete BEFORE DELETE ON d2_audit_entries BEGIN SELECT RAISE(ABORT, 'audit entries are append-only'); END"))

    @staticmethod
    def _configure_sqlite(connection, _record) -> None:
        cursor = connection.cursor(); cursor.execute("PRAGMA journal_mode=WAL"); cursor.execute("PRAGMA foreign_keys=ON"); cursor.close()

    @contextmanager
    def session(self):
        session = self.sessions()
        try:
            yield session; session.commit()
        except Exception:
            session.rollback(); raise
        finally:
            session.close()
