from __future__ import annotations
import hashlib, os, uuid
from sqlalchemy import select
from ..db import Derivative, utc_now
class DerivativeService:
    def __init__(self,config,database,audit,integrity): self.config,self.database,self.audit,self.integrity=config,database,audit,integrity
    def create(self,evidence_id,kind,data,suffix,transformation,parameters,tool_versions,actor):
        if self.integrity.verify(evidence_id,actor)["integrity_status"]!="Hash Match": raise ValueError("Parent evidence failed integrity verification")
        derivative_id=f"{evidence_id}-DRV-{uuid.uuid4().hex[:10].upper()}";folder=self.config.derivatives/evidence_id;folder.mkdir(parents=True,exist_ok=True);final=folder/f"{derivative_id}{suffix}";temporary=folder/f".{derivative_id}.tmp"
        with temporary.open("xb") as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,final);record=Derivative(id=derivative_id,evidence_id=evidence_id,kind=kind,storage_path=str(final),transformation=transformation,parameters=parameters,tool_versions=tool_versions,created_at=utc_now(),sha256=hashlib.sha256(data).hexdigest())
        with self.database.session() as session: session.add(record)
        self.audit.append(actor,"derivative.create",evidence_id,"success",{"derivative_id":derivative_id,"kind":kind,"sha256":record.sha256,"transformation":transformation,"parameters":parameters,"tool_versions":tool_versions});return record
    def list(self,evidence_id):
        with self.database.session() as session:return list(session.scalars(select(Derivative).where(Derivative.evidence_id==evidence_id).order_by(Derivative.created_at)))
