from __future__ import annotations
import json,uuid
from pathlib import Path
from fastapi import APIRouter,File,Form,HTTPException,Query,UploadFile
from fastapi.responses import FileResponse,HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from sqlalchemy import select
from ..analysis import CopyMoveAnalyzer,VideoContinuityAnalyzer
from ..db import AnalysisRun,Derivative,utc_now
from ..services import D2Services

router=APIRouter(tags=["D2 evidence authentication"]);services=D2Services();templates=Jinja2Templates(directory=str(Path(__file__).parents[1]/"ui"/"templates"))
D2_EN={"title":"Evidence Authentication & Tampering","description":"Classical evidence preservation, metadata inspection, and bounded manipulation observations. This module does not detect deepfakes or prove authenticity or tampering.","secure_intake":"Secure intake","case_id":"Case ID","demo_identity":"Demo identity","evidence_file":"Evidence file","receipt_context":"Receipt context","receipt_placeholder":"How and where was this evidence received?","preserve":"Preserve evidence","none_selected":"No evidence selected.","integrity":"Integrity Status","evidence_id":"Evidence ID","verify_hash":"Verify Hash","verify_audit":"Verify Audit Chain","hash_caveat":"Hash comparison is separate from content analysis and does not establish authenticity.","not_verified":"Not Yet Verified","metadata":"Metadata Summary","extract_metadata":"Extract metadata","software_caveat":"Software tag indicates declared association only; it does not prove original creator or intent.","camera_caveat":"No camera tag present – common for many sources. Missing camera tags are never evidence of tampering.","normalized":"Normalized","raw":"Raw","no_snapshot":"No snapshot extracted.","analysis":"Manipulation Analysis Results","method":"Method","copy_move":"Image copy-move localization","video_continuity":"Video continuity observation","mask":"Optional ground-truth mask","run_analysis":"Run bounded analysis","export":"Generate export package","copy_caveat":"Copy-move localization identifies possible duplicated regions. Repeated textures can cause false matches.","continuity_caveat":"Frame continuity observations are not comprehensive tampering authentication.","no_analysis":"No analysis run.","request_failed":"Request failed"}
D2_HI={"title":"साक्ष्य प्रमाणीकरण और छेड़छाड़","description":"पारंपरिक साक्ष्य संरक्षण, मेटाडेटा निरीक्षण और सीमित हेरफेर अवलोकन। यह मॉड्यूल डीपफेक का पता नहीं लगाता और प्रामाणिकता या छेड़छाड़ सिद्ध नहीं करता।","secure_intake":"सुरक्षित इनटेक","case_id":"केस आईडी","demo_identity":"डेमो पहचान","evidence_file":"साक्ष्य फ़ाइल","receipt_context":"प्राप्ति संदर्भ","receipt_placeholder":"यह साक्ष्य कैसे और कहाँ प्राप्त हुआ?","preserve":"साक्ष्य सुरक्षित करें","none_selected":"कोई साक्ष्य चयनित नहीं।","integrity":"अखंडता स्थिति","evidence_id":"साक्ष्य आईडी","verify_hash":"हैश सत्यापित करें","verify_audit":"ऑडिट शृंखला सत्यापित करें","hash_caveat":"हैश तुलना सामग्री विश्लेषण से अलग है और प्रामाणिकता स्थापित नहीं करती।","not_verified":"अभी सत्यापित नहीं","metadata":"मेटाडेटा सारांश","extract_metadata":"मेटाडेटा निकालें","software_caveat":"सॉफ़्टवेयर टैग केवल घोषित संबंध दिखाता है; यह मूल निर्माता या उद्देश्य सिद्ध नहीं करता।","camera_caveat":"कैमरा टैग मौजूद नहीं है—यह कई स्रोतों में सामान्य है। कैमरा टैग का न होना कभी भी छेड़छाड़ का प्रमाण नहीं है।","normalized":"सामान्यीकृत","raw":"मूल","no_snapshot":"कोई स्नैपशॉट नहीं निकाला गया।","analysis":"हेरफेर विश्लेषण परिणाम","method":"विधि","copy_move":"चित्र कॉपी-मूव स्थानीयकरण","video_continuity":"वीडियो निरंतरता अवलोकन","mask":"वैकल्पिक ग्राउंड-ट्रुथ मास्क","run_analysis":"सीमित विश्लेषण चलाएँ","export":"निर्यात पैकेज बनाएँ","copy_caveat":"कॉपी-मूव स्थानीयकरण संभावित दोहराए गए क्षेत्र पहचानता है। दोहराव वाली बनावट गलत मेल पैदा कर सकती है।","continuity_caveat":"फ़्रेम निरंतरता अवलोकन व्यापक छेड़छाड़ प्रमाणीकरण नहीं हैं।","no_analysis":"कोई विश्लेषण नहीं चला।","request_failed":"अनुरोध विफल"}
D2_EN.update({"choose_file":"Choose file","no_file_chosen":"No file chosen"});D2_HI.update({"choose_file":"फ़ाइल चुनें","no_file_chosen":"कोई फ़ाइल नहीं चुनी गई"})
def actor(value): return (value or services.config.demo_identity).strip()[:200]
def evidence_json(item): return {"evidence_id":item.id,"case_id":item.case_id,"original_filename":item.original_filename,"sha256":item.sha256,"byte_size":item.byte_size,"received_at":item.received_at,"receipt_context":item.receipt_context,"uploader_identity":item.uploader_identity,"integrity_status":item.integrity_status}
def derivative_json(item): return {"derivative_id":item.id,"parent_evidence_id":item.evidence_id,"kind":item.kind,"transformation":item.transformation,"parameters":item.parameters,"tool_versions":item.tool_versions,"created_at":item.created_at,"sha256":item.sha256}
def fail(error):
    if isinstance(error,KeyError): raise HTTPException(404,"D2 evidence was not found")
    if isinstance(error,ValueError): raise HTTPException(422,str(error))
    raise error

@router.get("/d2",response_class=HTMLResponse,include_in_schema=False)
def d2_page(request:Request,embedded:bool=Query(False),theme:str=Query("light"),lang:str=Query("en")):
    language="hi" if lang=="hi" else "en";copy={**D2_EN,**(D2_HI if language=="hi" else {})}
    return templates.TemplateResponse(request,"d2.html",{"identity":services.config.demo_identity,"embedded":embedded,"theme":"dark" if theme=="dark" else "light","lang":language,"t":copy})
@router.post("/api/d2/evidence",status_code=201)
async def intake(file:UploadFile=File(...),case_id:str=Form(...),receipt_context:str=Form(""),demo_identity:str|None=Form(None)):
    try:return evidence_json(await services.intake.intake(case_id,file,receipt_context,actor(demo_identity)))
    except Exception as error: fail(error)
@router.get("/api/d2/evidence")
def list_evidence(case_id:str|None=Query(None)): return {"items":[evidence_json(item) for item in services.intake.list(case_id)]}
@router.get("/api/d2/evidence/{evidence_id}")
def read_evidence(evidence_id:str):
    try:return {**evidence_json(services.intake.get(evidence_id)),"derivatives":[derivative_json(item) for item in services.derivatives.list(evidence_id)]}
    except Exception as error: fail(error)
@router.post("/api/d2/evidence/{evidence_id}/verify")
def verify(evidence_id:str,demo_identity:str|None=Form(None)):
    try:return services.integrity.verify(evidence_id,actor(demo_identity))
    except Exception as error: fail(error)
@router.post("/api/d2/evidence/{evidence_id}/metadata")
def metadata(evidence_id:str,demo_identity:str|None=Form(None)):
    try:
        item=services.metadata.extract(evidence_id,actor(demo_identity));return {"snapshot_id":item.id,"extracted_at":item.extracted_at,"raw":item.raw,"normalized":item.normalized,"tool_versions":item.tool_versions}
    except Exception as error: fail(error)
def save_analysis(evidence_id,result,who):
    artifact_ids=[]
    for artifact in result.artifacts:
        record=services.derivatives.create(evidence_id,artifact["kind"],artifact["bytes"],artifact["suffix"],result.algorithm,result.parameters,{"method":result.version},who);artifact_ids.append(record.id)
    run=AnalysisRun(id=f"D2RUN-{uuid.uuid4().hex}",evidence_id=evidence_id,method=result.algorithm,method_version=result.version,created_at=utc_now(),format_support=result.format_support,decoding=result.decoding,analysis=result.analysis,parameters=result.parameters,findings=result.findings,interpretation=result.interpretation,limitations=result.limitations,artifacts=artifact_ids,evaluation=result.evaluation)
    with services.database.session() as session:session.add(run)
    services.audit.append(who,"analysis.run",evidence_id,"success" if result.analysis in {"Completed","Partial"} else "failure",{"run_id":run.id,"method":run.method,"statuses":{"format_support":run.format_support,"decoding":run.decoding,"analysis":run.analysis}})
    return {"run_id":run.id,"evidence_id":evidence_id,**result.dict(),"artifacts":[{"derivative_id":item,"download_url":f"/api/d2/derivatives/{item}","verify_parent_url":f"/api/d2/derivatives/{item}/verify-parent"} for item in artifact_ids]}
@router.post("/api/d2/evidence/{evidence_id}/analysis/copy-move")
def copy_move(evidence_id:str,ground_truth_mask:UploadFile|None=File(None),block_size:int=Form(16),step:int=Form(8),min_cluster:int=Form(3),demo_identity:str|None=Form(None)):
    try:
        evidence=services.intake.get(evidence_id);truth=None
        if ground_truth_mask:
            import io;truth=io.BytesIO(ground_truth_mask.file.read())
        return save_analysis(evidence_id,CopyMoveAnalyzer(block_size,step,min_cluster=min_cluster).analyze(evidence.storage_path,truth),actor(demo_identity))
    except Exception as error: fail(error)
@router.post("/api/d2/evidence/{evidence_id}/analysis/video-continuity")
def video_continuity(evidence_id:str,sample_fps:float=Form(1.0),max_frames:int=Form(120),max_duration_seconds:float=Form(120),ground_truth_json:str|None=Form(None),demo_identity:str|None=Form(None)):
    try:
        evidence=services.intake.get(evidence_id);truth=json.loads(ground_truth_json) if ground_truth_json else None
        return save_analysis(evidence_id,VideoContinuityAnalyzer(sample_fps,max_frames,max_duration_seconds).analyze(evidence.storage_path,truth),actor(demo_identity))
    except (json.JSONDecodeError,TypeError): raise HTTPException(422,"ground_truth_json must be a JSON list of frame-index pairs")
    except Exception as error: fail(error)
@router.get("/api/d2/evidence/{evidence_id}/analysis")
def analyses(evidence_id:str):
    try:services.intake.get(evidence_id)
    except Exception as error:fail(error)
    with services.database.session() as session:
        items=list(session.scalars(select(AnalysisRun).where(AnalysisRun.evidence_id==evidence_id).order_by(AnalysisRun.created_at.desc())))
        return {"items":[{"run_id":x.id,"method":x.method,"method_version":x.method_version,"statuses":{"format_support":x.format_support,"decoding":x.decoding,"analysis":x.analysis},"parameters":x.parameters,"findings":x.findings,"interpretation":x.interpretation,"limitations":x.limitations,"artifacts":x.artifacts,"evaluation":x.evaluation} for x in items]}
@router.get("/api/d2/derivatives/{derivative_id}")
def derivative(derivative_id:str):
    with services.database.session() as session:item=session.get(Derivative,derivative_id)
    if not item:raise HTTPException(404,"Derivative was not found")
    return FileResponse(item.storage_path,filename=Path(item.storage_path).name)
@router.post("/api/d2/derivatives/{derivative_id}/verify-parent")
def verify_derivative_parent(derivative_id:str,demo_identity:str|None=Form(None)):
    with services.database.session() as session:item=session.get(Derivative,derivative_id)
    if not item:raise HTTPException(404,"Derivative was not found")
    return services.integrity.verify(item.evidence_id,actor(demo_identity))
@router.get("/api/d2/audit")
def audit(evidence_id:str|None=Query(None)): return {"items":[{k:getattr(x,k) for k in ("sequence","actor","action_type","evidence_id","timestamp","result","parameters","previous_hash","entry_hash")} for x in services.audit.list(evidence_id)]}
@router.post("/api/d2/audit/verify")
def verify_audit(): return services.audit.verify()
@router.post("/api/d2/evidence/{evidence_id}/export")
def export(evidence_id:str,demo_identity:str|None=Form(None)):
    try:return FileResponse(services.exports.create(evidence_id,actor(demo_identity)),media_type="application/zip",filename=f"{evidence_id}-export.zip")
    except Exception as error:fail(error)
