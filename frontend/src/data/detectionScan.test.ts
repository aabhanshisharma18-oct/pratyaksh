import {afterEach,describe,expect,it,vi} from 'vitest';
import {scanFile} from './detectionScan';

const evidence = {id:'E-1',name:'face.png',type:'image' as const,hash:'a'.repeat(64)};
function response() {
  return {
    run_id:'R-1',evidence_id:evidence.id,sha256:evidence.hash,
    findings:[{
      schema_version:'1.1',finding_id:'F-1',run_id:'R-1',evidence_id:evidence.id,
      category:'synthetic_media',execution_status:'completed',result:'inconclusive',
      observation:'Face scored',method:'SBI',method_version:'test',scope:'Face crop',
      score:null,location:null,support_refs:[],limitations:[],review_status:'unreviewed',fixture:false,
    }],
    face_analysis:{
      finding_id:'F-1',width:100,height:100,execution_status:'completed',face_count:1,faces_truncated:false,
      faces:[{bbox_xyxy:[10,20,70,90],detection_confidence:.9,face_forgery_score:.8}],
    },
    summary:{result:'inconclusive',completed_checks:1,total_checks:1,reason:'Uncalibrated'},
  };
}
function serve(body: unknown) {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>body}));
}
afterEach(()=>vi.unstubAllGlobals());

describe('SBI scan responses',()=>{
  it('keeps per-face coordinates and scores',async()=>{
    serve(response());
    const scan=await scanFile('http://localhost',new Blob(['test']),evidence);
    expect(scan.face_analysis?.faces[0].bbox_xyxy).toEqual([10,20,70,90]);
    expect(scan.face_analysis?.faces[0].face_forgery_score).toBe(.8);
  });
  it('accepts older scan results without face analysis',async()=>{
    const {face_analysis,...older}=response();
    serve(older);
    expect((await scanFile('http://localhost',new Blob(['test']),evidence)).face_analysis).toBeUndefined();
  });
  it('rejects face boxes outside the evidence image',async()=>{
    const body=response();
    body.face_analysis.faces[0].bbox_xyxy=[10,20,120,90];
    serve(body);
    await expect(scanFile('http://localhost',new Blob(['test']),evidence)).rejects.toThrow('unexpected scan result');
  });
  it('rejects faces linked to an unknown finding',async()=>{
    const body=response();
    body.face_analysis.finding_id='F-OTHER';
    serve(body);
    await expect(scanFile('http://localhost',new Blob(['test']),evidence)).rejects.toThrow('could not be matched');
  });
  it('accepts a completed check that detected no faces',async()=>{
    serve({...response(),face_analysis:{
      finding_id:'F-1',width:100,height:100,execution_status:'no_face',face_count:0,faces:[],
    }});
    const scan=await scanFile('http://localhost',new Blob(['test']),evidence);
    expect(scan.face_analysis?.execution_status).toBe('no_face');
    expect(scan.face_analysis?.faces).toEqual([]);
  });
});
