"""Reset and seed an isolated, repeatable D4 demonstration database."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from cases.repository import CaseRepository  # noqa: E402

FIXED_TIME = "2026-11-12T09:00:00.000Z"


def seed(database: Path) -> dict:
    database = database.resolve()
    protected = (BACKEND / "data" / "pratyaksh.db").resolve()
    if database == protected:
        raise SystemExit("Refusing to reset the default developer database; choose a D4 demo path.")
    database.parent.mkdir(parents=True, exist_ok=True)
    for target in (database, Path(str(database) + "-wal"), Path(str(database) + "-shm")):
        target.unlink(missing_ok=True)
    repository = CaseRepository(database)
    case = repository.create_case("D4 Demonstration", "Deterministic reviewer walkthrough", "Demo analyst")
    fixture = ROOT / "e2e" / "fixtures" / "valid.png"
    payload = fixture.read_bytes()
    evidence = repository.register_evidence(case["id"], {
        "evidence_id": "EVID-D4-IMAGE", "filename": "valid.png", "media_type": "image",
        "role": "Evidence", "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }, "Demo analyst")
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE cases SET created_at = ?, last_activity_at = ?", (FIXED_TIME, FIXED_TIME))
        connection.execute("UPDATE case_evidence SET registered_at = ?", (FIXED_TIME,))
        connection.execute("UPDATE case_events SET created_at = ?", (FIXED_TIME,))
        connection.commit()
    result = {"database": str(database), "case_id": case["id"], "case_title": case["title"],
              "evidence_id": evidence["evidence_id"], "filename": evidence["filename"],
              "sha256": evidence["sha256"], "fixed_time": FIXED_TIME}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=BACKEND / "data" / "d4-demo.db")
    seed(parser.parse_args().database)
