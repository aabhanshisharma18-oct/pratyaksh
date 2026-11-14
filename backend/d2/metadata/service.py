from __future__ import annotations
import json, shutil, subprocess, uuid
from importlib.metadata import version
from pathlib import Path
from PIL import Image, ExifTags
from sqlalchemy import select
from ..db import MetadataSnapshot, utc_now

CAMERA_NEUTRAL="No camera tag present – common for many sources"
SOFTWARE_LIMIT="Software tag indicates declared association only; it does not prove original creator or intent."
CAMERA_LIMIT="Missing camera tags are never evidence of tampering."

def command_json(command):
    result=subprocess.run(command,capture_output=True,text=True,timeout=60,check=True)
    return json.loads(result.stdout), (result.stderr or "").strip()

class MetadataService:
    def __init__(self,database,audit,intake): self.database,self.audit,self.intake=database,audit,intake
    def extract(self,evidence_id,actor):
        evidence=self.intake.get(evidence_id);path=Path(evidence.storage_path);raw={};tools={};errors=[]
        exiftool=shutil.which("exiftool")
        if exiftool:
            try: value,_=command_json([exiftool,"-j","-G","-n",str(path)]);raw["exiftool"]=value[0] if value else {};tools["exiftool"]=subprocess.run([exiftool,"-ver"],capture_output=True,text=True,timeout=10).stdout.strip()
            except Exception as error: errors.append(f"ExifTool extraction failed: {type(error).__name__}")
        ffprobe=shutil.which("ffprobe")
        if ffprobe:
            try: value,_=command_json([ffprobe,"-v","error","-show_format","-show_streams","-of","json",str(path)]);raw["ffprobe"]=value;tools["ffprobe"]=subprocess.run([ffprobe,"-version"],capture_output=True,text=True,timeout=10).stdout.splitlines()[0]
            except Exception as error: errors.append(f"ffprobe extraction failed: {type(error).__name__}")
        try:
            with Image.open(path) as image:
                exif={ExifTags.TAGS.get(key,str(key)):str(value) for key,value in image.getexif().items()}
                raw["pillow"]={"format":image.format,"mode":image.mode,"width":image.width,"height":image.height,"exif":exif};tools["Pillow"]=version("Pillow")
        except Exception: pass
        exif=raw.get("exiftool",{});pillow=raw.get("pillow",{});probe=raw.get("ffprobe",{});fmt=probe.get("format",{});streams=probe.get("streams",[])
        pick=lambda *names: next((exif[name] for name in names if name in exif and exif[name] not in (None,"")),None)
        camera=" ".join(filter(None,[pick("EXIF:Make","Make"),pick("EXIF:Model","Model")])).strip() or CAMERA_NEUTRAL
        normalized={"timestamps":{"creation":pick("EXIF:DateTimeOriginal","QuickTime:CreateDate","CreateDate"),"modification":pick("File:FileModifyDate","ModifyDate"),"digitization":pick("EXIF:CreateDate","DateTimeDigitized"),"timezone":pick("EXIF:OffsetTimeOriginal","OffsetTimeOriginal") or "Not recorded"},"software":pick("EXIF:Software","Software","XMP:CreatorTool") or "Not recorded","camera":camera,"dimensions":{"width":pillow.get("width") or pick("File:ImageWidth","ImageWidth"),"height":pillow.get("height") or pick("File:ImageHeight","ImageHeight")},"container":{"format":fmt.get("format_name") or pillow.get("format") or "Unknown","duration_seconds":fmt.get("duration"),"bit_rate":fmt.get("bit_rate"),"streams":[{"index":s.get("index"),"type":s.get("codec_type"),"codec":s.get("codec_name"),"width":s.get("width"),"height":s.get("height"),"sample_rate":s.get("sample_rate"),"channels":s.get("channels"),"bit_rate":s.get("bit_rate")} for s in streams]},"limitations":[SOFTWARE_LIMIT,CAMERA_LIMIT],"tool_errors":errors}
        snapshot=MetadataSnapshot(id=f"META-{uuid.uuid4().hex}",evidence_id=evidence_id,extracted_at=utc_now(),raw=raw,normalized=normalized,tool_versions=tools)
        with self.database.session() as session: session.add(snapshot)
        self.audit.append(actor,"metadata.extract",evidence_id,"success" if raw else "failure",{"snapshot_id":snapshot.id,"tool_versions":tools,"errors":errors});return snapshot
    def latest(self,evidence_id):
        with self.database.session() as session:return session.scalars(select(MetadataSnapshot).where(MetadataSnapshot.evidence_id==evidence_id).order_by(MetadataSnapshot.extracted_at.desc()).limit(1)).first()
