from __future__ import annotations
import hashlib, os, re, uuid
from fastapi import UploadFile
from sqlalchemy import select, text
from ..db import CaseCounter, Evidence, utc_now
CASE_PATTERN=re.compile(r"^CASE-(\d{4})-(\d{3,6})$")

class IntakeService:
    def __init__(self,config,database,audit): self.config,self.database,self.audit=config,database,audit
    def reserve_id(self,case_id):
        if not CASE_PATTERN.fullmatch(case_id): raise ValueError("case_id must use CASE-YYYY-NNN or CASE-YYYY-NNNNNN")
        with self.database.session() as session:
            session.execute(text("BEGIN IMMEDIATE")); counter=session.get(CaseCounter,case_id)
            if counter is None: counter=CaseCounter(case_id=case_id,next_value=2);session.add(counter);number=1
            else: number=counter.next_value;counter.next_value+=1
            session.flush()
        return f"{case_id}-EVD-{number:05d}"
    async def intake(self,case_id,upload,receipt_context,actor):
        evidence_id=self.reserve_id(case_id);folder=self.config.originals/evidence_id;folder.mkdir(parents=True,exist_ok=False);temporary=folder/f".{uuid.uuid4().hex}.upload";final=folder/"original.bin";digest=hashlib.sha256();size=0
        try:
            with temporary.open("xb") as stream:
                while chunk:=await upload.read(1024*1024):
                    size+=len(chunk)
                    if size>self.config.max_upload_bytes: raise ValueError("Upload exceeds configured D2 limit")
                    digest.update(chunk);stream.write(chunk)
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,final);os.chmod(final,0o444)
            evidence=Evidence(id=evidence_id,case_id=case_id,original_filename=upload.filename or "unnamed",storage_path=str(final),sha256=digest.hexdigest(),byte_size=size,received_at=utc_now(),receipt_context=receipt_context,uploader_identity=actor,integrity_status="Not Yet Verified")
            with self.database.session() as session: session.add(evidence)
            self.audit.append(actor,"evidence.intake",evidence_id,"success",{"byte_size":size,"sha256":evidence.sha256,"original_filename":evidence.original_filename});return evidence
        except Exception as error:
            temporary.unlink(missing_ok=True);self.audit.append(actor,"evidence.intake",evidence_id,"failure",{"error":type(error).__name__});raise
    def get(self,evidence_id):
        with self.database.session() as session:
            evidence=session.get(Evidence,evidence_id)
            if not evidence: raise KeyError(evidence_id)
            return evidence
    def list(self,case_id=None):
        with self.database.session() as session:
            query=select(Evidence).order_by(Evidence.received_at.desc())
            if case_id: query=query.where(Evidence.case_id==case_id)
            return list(session.scalars(query))
