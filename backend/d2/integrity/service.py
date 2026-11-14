from __future__ import annotations
import hashlib
from pathlib import Path
from ..db import D2Database, Evidence

def sha256_file(path: Path, chunk_size=1024*1024):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(chunk_size),b""): digest.update(chunk)
    return digest.hexdigest()

class IntegrityService:
    def __init__(self,database,audit): self.database,self.audit=database,audit
    def verify(self,evidence_id,actor):
        with self.database.session() as session:
            evidence=session.get(Evidence,evidence_id)
            if not evidence: raise KeyError(evidence_id)
            path=Path(evidence.storage_path); actual=sha256_file(path) if path.is_file() else None; status="Hash Match" if actual==evidence.sha256 else "Hash Mismatch"; evidence.integrity_status=status; expected=evidence.sha256
        self.audit.append(actor,"integrity.verify",evidence_id,"success",{"status":status,"expected_sha256":expected,"actual_sha256":actual})
        return {"evidence_id":evidence_id,"integrity_status":status,"expected_sha256":expected,"actual_sha256":actual}
