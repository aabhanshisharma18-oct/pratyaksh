from __future__ import annotations
import hashlib,json,os,tempfile,zipfile
from pathlib import Path
from sqlalchemy import select
from ..db import AnalysisRun, MetadataSnapshot
from ..integrity import sha256_file

GENERAL_LIMITATIONS=["Integrity status reports byte-level comparison only and does not establish authenticity.","Content-analysis observations are bounded method outputs, not proof of tampering or synthetic-media detection."]

def json_bytes(value): return json.dumps(value,indent=2,sort_keys=True,default=str,ensure_ascii=False).encode("utf-8")

class ExportService:
    def __init__(self,config,database,audit,intake,integrity,derivatives): self.config,self.database,self.audit,self.intake,self.integrity,self.derivatives=config,database,audit,intake,integrity,derivatives
    def create(self,evidence_id,actor):
        evidence=self.intake.get(evidence_id);verification=self.integrity.verify(evidence_id,actor)
        with self.database.session() as session:
            metadata=session.scalars(select(MetadataSnapshot).where(MetadataSnapshot.evidence_id==evidence_id).order_by(MetadataSnapshot.extracted_at.desc()).limit(1)).first();analyses=list(session.scalars(select(AnalysisRun).where(AnalysisRun.evidence_id==evidence_id).order_by(AnalysisRun.created_at)))
        audit=self.audit.list(evidence_id);files={"original/original.bin":Path(evidence.storage_path).read_bytes(),"integrity/verification.json":json_bytes(verification),"metadata/snapshot.json":json_bytes({"raw":metadata.raw,"normalized":metadata.normalized,"tool_versions":metadata.tool_versions,"extracted_at":metadata.extracted_at} if metadata else {"status":"not_extracted"}),"audit/events.json":json_bytes([{k:getattr(item,k) for k in ("sequence","actor","action_type","evidence_id","timestamp","result","parameters","previous_hash","entry_hash")} for item in audit]),"limitations.json":json_bytes(GENERAL_LIMITATIONS)}
        for run in analyses: files[f"analysis/{run.id}.json"]=json_bytes({"id":run.id,"method":run.method,"method_version":run.method_version,"statuses":{"format_support":run.format_support,"decoding":run.decoding,"analysis":run.analysis},"parameters":run.parameters,"findings":run.findings,"interpretation":run.interpretation,"limitations":run.limitations,"artifacts":run.artifacts,"evaluation":run.evaluation})
        for derivative in self.derivatives.list(evidence_id): files[f"derivatives/{Path(derivative.storage_path).name}"]=Path(derivative.storage_path).read_bytes()
        manifest={"evidence_id":evidence_id,"integrity_status":verification["integrity_status"],"note":"manifest.json is excluded from its own hash list to avoid recursive self-reference.","files":[{"path":name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)} for name,data in sorted(files.items())]};files["manifest.json"]=json_bytes(manifest)
        destination=self.config.exports/f"{evidence_id}-export.zip";temporary=destination.with_suffix(".tmp")
        with zipfile.ZipFile(temporary,"w",zipfile.ZIP_DEFLATED) as archive:
            for name,data in files.items(): archive.writestr(name,data)
        os.replace(temporary,destination);self.audit.append(actor,"evidence.export",evidence_id,"success",{"package":destination.name,"sha256":sha256_file(destination),"integrity_status":verification["integrity_status"]});return destination
