import {z} from 'zod';
import {findingSchema, type Evidence} from '../model';

const faceAnalysisSchema = z.object({
  finding_id: z.string(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  execution_status: z.enum(['completed','no_face']),
  face_count: z.number().int().min(0).max(8),
  faces_truncated: z.boolean().default(false),
  faces: z.array(z.object({
    bbox_xyxy: z.tuple([z.number().finite(),z.number().finite(),z.number().finite(),z.number().finite()]),
    detection_confidence: z.number().min(0).max(1),
    face_forgery_score: z.number().min(0).max(1),
  })).max(8),
}).superRefine((analysis,context)=>{
  if (analysis.face_count!==analysis.faces.length || (analysis.execution_status==='no_face')!==(analysis.faces.length===0)) {
    context.addIssue({code:'custom',message:'Face counts do not match the analysis status.'});
  }
  for (const face of analysis.faces) {
    const [left,top,right,bottom]=face.bbox_xyxy;
    if (left<0 || top<0 || right>analysis.width || bottom>analysis.height || right<=left || bottom<=top) {
      context.addIssue({code:'custom',message:'Invalid face coordinates.'});
    }
  }
});
export type FaceAnalysis = z.infer<typeof faceAnalysisSchema>;

const scanSchema = z.object({
  run_id: z.string(),
  evidence_id: z.string(),
  sha256: z.string(),
  findings: z.array(findingSchema),
  face_analysis: faceAnalysisSchema.optional(),
  summary: z.object({result:z.enum(['inconclusive','unavailable']), completed_checks:z.number(), total_checks:z.number(), reason:z.string()}),
});
export type DetectionScan = z.infer<typeof scanSchema>;

export async function scanEvidence(base: string, evidence: Evidence): Promise<DetectionScan> {
  if (!evidence.source || evidence.type === 'video') throw new Error('This scan requires an available image or audio file.');
  const media = await fetch(evidence.source);
  if (!media.ok) throw new Error('The evidence file could not be read.');
  return scanFile(base, await media.blob(), evidence);
}

export async function scanFile(base: string, file: Blob, evidence: Pick<Evidence, 'id'|'name'|'type'|'hash'>): Promise<DetectionScan> {
  if (evidence.type === 'video') throw new Error('This scan supports images and audio.');
  const form = new FormData();
  form.set('file', file, evidence.name);
  form.set('evidence_id', evidence.id);
  form.set('media_type', evidence.type);
  const useDevProxy = import.meta.env.DEV && base === import.meta.env.VITE_D1_API_BASE_URL?.trim();
  const endpoint = (useDevProxy ? '' : base.replace(/\/$/, '')) + '/api/d1/scan';
  let response: Response;
  try {
    response = await fetch(endpoint, {method:'POST', body:form});
  } catch {
    throw new Error('Could not connect to the detection API. Check that the workspace and backend are running, then retry.');
  }
  if (!response.ok) {
    const body = await response.json().catch(()=>null);
    if (typeof body?.detail === 'string') throw new Error(body.detail);
    if (useDevProxy && response.status >= 500 && !body) {
      throw new Error('The workspace could not reach the local detection backend (HTTP '+response.status+'). Check that it is running at '+base+'.');
    }
    throw new Error('The detection API returned HTTP '+response.status+'.');
  }
  const payload: unknown = await response.json().catch(()=>null);
  const parsed = scanSchema.safeParse(payload);
  if (!parsed.success) throw new Error('The detection API returned an unexpected scan result.');
  const scan = parsed.data;
  if (scan.evidence_id !== evidence.id || scan.sha256 !== evidence.hash.toLowerCase() ||
      scan.findings.some(item=>item.run_id!==scan.run_id || item.evidence_id!==evidence.id) ||
      (scan.face_analysis && !scan.findings.some(item=>item.finding_id===scan.face_analysis?.finding_id))) {
    throw new Error('The returned scan could not be matched to the recorded evidence hash and ID.');
  }
  return scan;
}

export async function scanLocalFile(base: string, file: File, type: 'image'|'audio') {
  if (!crypto.subtle) throw new Error('Open the workspace on localhost or HTTPS to calculate the evidence hash.');
  const bytes = await file.arrayBuffer().catch(()=>{ throw new Error('The evidence file could not be read. Reopen it and retry.'); });
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const hash = Array.from(new Uint8Array(digest), byte=>byte.toString(16).padStart(2,'0')).join('');
  return scanFile(base,file,{id:'TEST-'+crypto.randomUUID(),name:file.name,type,hash});
}

const videoScanSchema = z.object({
  finding: z.object({run_id:z.string(),method:z.string(),method_version:z.string(),limitations:z.array(z.string())}),
  sampling: z.object({
    requested_samples:z.number().int().positive(),
    rejected_samples:z.array(z.object({timestamp_ms:z.number().int().nonnegative().nullable(),reason:z.string()})),
  }),
  samples:z.array(z.object({
    sample_id:z.string(),timestamp_ms:z.number().int().nonnegative(),deepfake_score:z.number().min(0).max(1),
  })).min(1),
  aggregation:z.object({mean_score:z.number().min(0).max(1),maximum_score:z.number().min(0).max(1)}),
});
export type VideoDetectionScan = z.infer<typeof videoScanSchema>;

export async function scanLocalVideo(base:string,file:File,signal:AbortSignal):Promise<VideoDetectionScan> {
  const form = new FormData();
  form.set('file',file);
  const useDevProxy = import.meta.env.DEV && base === import.meta.env.VITE_D1_API_BASE_URL?.trim();
  let response:Response;
  try {
    response = await fetch((useDevProxy?'':base.replace(/\/$/,''))+'/api/d1/analyze-video',
      {method:'POST',body:form,signal});
  } catch {
    throw new Error('Could not connect to the detection backend. Check that it is running, then retry.');
  }
  const body = await response.json().catch(()=>null);
  if (!response.ok) {
    throw new Error(typeof body?.detail==='string'?body.detail:'Video scan failed (HTTP '+response.status+').');
  }
  const parsed = videoScanSchema.safeParse(body);
  if (!parsed.success) throw new Error('The backend returned an unexpected video scan result.');
  return parsed.data;
}
