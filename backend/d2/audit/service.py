from __future__ import annotations
import hashlib, json
from datetime import timezone
from sqlalchemy import select, text
from ..db import AuditEntry, D2Database, utc_now

def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()

class AuditService:
    def __init__(self, database: D2Database): self.database = database
    @staticmethod
    def body(value) -> dict:
        if isinstance(value, AuditEntry):
            value={"sequence":value.sequence,"actor":value.actor,"action_type":value.action_type,"evidence_id":value.evidence_id,"timestamp":value.timestamp,"result":value.result,"parameters":value.parameters,"previous_hash":value.previous_hash}
        timestamp=value["timestamp"]
        if hasattr(timestamp,"astimezone"):
            if timestamp.tzinfo is None: timestamp=timestamp.replace(tzinfo=timezone.utc)
            timestamp=timestamp.astimezone(timezone.utc).isoformat()
        return {**value,"timestamp":str(timestamp)}
    def append(self, actor, action_type, evidence_id, result, parameters=None):
        with self.database.session() as session:
            session.execute(text("BEGIN IMMEDIATE")); previous=session.scalars(select(AuditEntry).order_by(AuditEntry.sequence.desc()).limit(1)).first(); timestamp=utc_now(); sequence=(previous.sequence if previous else 0)+1
            body={"sequence":sequence,"actor":actor,"action_type":action_type,"evidence_id":evidence_id,"timestamp":timestamp,"result":result,"parameters":parameters or {},"previous_hash":previous.entry_hash if previous else "0"*64}
            entry=AuditEntry(**body,entry_hash=hashlib.sha256(canonical(self.body(body))).hexdigest()); session.add(entry); session.flush(); return entry
    def list(self,evidence_id=None):
        with self.database.session() as session:
            query=select(AuditEntry).order_by(AuditEntry.sequence)
            if evidence_id: query=query.where(AuditEntry.evidence_id==evidence_id)
            return list(session.scalars(query))
    def verify(self):
        entries=self.list(); previous="0"*64
        for entry in entries:
            if entry.previous_hash!=previous or entry.entry_hash!=hashlib.sha256(canonical(self.body(entry))).hexdigest(): return {"valid":False,"broken_at":entry.sequence,"message":"Audit hash chain verification failed."}
            previous=entry.entry_hash
        return {"valid":True,"broken_at":None,"entries":len(entries),"head":previous}
