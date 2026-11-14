import {z} from 'zod';
import {evidenceReceiptSchema} from '../model';

export const region = z.tuple([z.number(),z.number(),z.number(),z.number()]);
const support = z.object({
  matched_features:z.number(), candidate_features:z.number(), geometric_inlier_ratio:z.number(),
  left_coverage:z.number(), right_coverage:z.number(), left_region:region, right_region:region,
  method:z.string(), point_pairs:z.array(region).optional(), frame_timestamps_ms:z.tuple([z.number(),z.number()]).optional(), sample_pair_count:z.number().optional(),
  homography:z.array(z.array(z.number())).optional(),
  hash_distance:z.number().nullable().optional(),candidate_search:z.string().optional(),
}).passthrough();
export const provenanceReportSchema = z.object({
  schema_version:z.literal('1.0'), analysis_id:z.string(), analyzed_at:z.string(),
  images:z.array(z.object({
    id:z.string(), filename:z.string(), sha256:z.string(), size_bytes:z.number(),
    case_evidence_id:z.string().optional(),
    case_intake:z.object({registered_at:z.string(),registered_by:z.string(),
      registered_by_verified:z.literal(false),receipt:evidenceReceiptSchema.nullish()}).optional(),
    video_coverage:z.object({duration_ms:z.number(),source_frame_timestamps:z.number(),requested_count:z.number(),examined_timestamps_ms:z.array(z.number()),rejected:z.array(z.object({timestamp_ms:z.number(),reason:z.string()}))}).optional(),
    comparison_area:region.optional(), format:z.string(), media_type:z.enum(['image','audio','video']).default('image'), width:z.number(), height:z.number(),
    metadata:z.record(z.string(),z.string()), metadata_flags:z.array(z.string()).default([]), metadata_method:z.string().optional(),
    detector_signals:z.array(z.any()).default([]),source_observation:z.string(), metadata_status:z.string(),
    content_credentials:z.object({status:z.string(),observation:z.string(),
      trust_policy:z.string().optional(),signature:z.string().optional(),content_binding:z.string().optional(),signer_trust:z.string().optional(),
      signer:z.record(z.string(),z.any()).optional(),tools:z.array(z.any()).optional(),actions:z.array(z.any()).optional(),
      validation_status:z.array(z.any()).optional(),validation_state:z.string().optional()}).passthrough(),
  }).passthrough()),
  relationships:z.array(z.object({
    id:z.string(), left_id:z.string(), right_id:z.string(),
    kind:z.enum(['exact_copy','matching_content','shared_metadata','shared_credentials']), explanation:z.string(), support:support.nullable(),
    metadata_fields:z.record(z.string(),z.string()).optional(),manifest_labels:z.array(z.string()).optional(),
  }).passthrough()),
  compared_pairs:z.number(), visual_matching_available:z.boolean(),
  pair_selection:z.object({
    strategy:z.enum(['exhaustive','cp_sat']),solver_status:z.string(),requested_budget:z.number().nullable(),
    planning_runtime_ms:z.number(),total_pairs:z.number(),cheap_checked_pairs:z.number(),
    eligible_visual_pairs:z.number(),selected_visual_pairs:z.number(),scope:z.string(),limitation:z.string(),
    exact_pairs:z.array(z.object({left_id:z.string(),right_id:z.string()})),
    selected_pairs:z.array(z.object({left_id:z.string(),right_id:z.string()})),
    unexamined_pairs:z.array(z.object({left_id:z.string(),right_id:z.string()})),
    unsupported_visual_pairs:z.array(z.object({left_id:z.string(),right_id:z.string()})),
  }).passthrough().optional(),
  methods:z.object({
    hash:z.string(),metadata:z.string(),visual:z.string(),
    opencv_version:z.string().nullable(),python_version:z.string(),
  }).passthrough(),
  limitations:z.array(z.string()),
  case:z.object({id:z.string(),title:z.string(),analyst:z.string()}).passthrough(),
  integrity:z.object({anchor_sequence:z.number(),anchor_hash:z.string(),storage:z.string(),log_scope:z.string(),limitations:z.string()}),
  report_sha256:z.string(),
  review_notes:z.array(z.object({author:z.string(),timestamp:z.string(),text:z.string(),scope_id:z.string().nullable(),analysis_id:z.string().optional()}).passthrough()).default([]),
  exact_duplicate_groups:z.array(z.array(z.string())).default([]),
}).passthrough();
export type ProvenanceReport = z.infer<typeof provenanceReportSchema>;
export type ProvenanceImage = ProvenanceReport['images'][number];
export type ProvenanceRelationship = ProvenanceReport['relationships'][number];

export async function analyzeProvenance(base: string, files: File[], signal: AbortSignal, context: {caseId:string;title:string;analyst:string}, areas?: Array<z.infer<typeof region>|null>, pairBudget?:number) {
  const body = new FormData();
  for (const file of files) body.append('files',file);
  if (areas) body.set('comparison_areas', JSON.stringify(areas));
  if (pairBudget!==undefined) body.set('pair_budget',String(pairBudget));
  body.set('case_id',context.caseId);body.set('case_title',context.title);body.set('analyst',context.analyst);
  const endpoint = import.meta.env.DEV && base === import.meta.env.VITE_D1_API_BASE_URL?.trim()
    ? '/api/d1/provenance/analyze' : base.replace(/\/$/,'')+'/api/d1/provenance/analyze';
  const response = await fetch(endpoint,{method:'POST',body,signal});
  if (!response.ok) {
    const error = await response.json().catch(()=>null);
    throw new Error(typeof error?.detail==='string' ? error.detail : 'The provenance comparison could not be completed.');
  }
  return provenanceReportSchema.parse(await response.json());
}

export function provenanceEndpoint(base:string,path:string) {
  return import.meta.env.DEV && base === import.meta.env.VITE_D1_API_BASE_URL?.trim()
    ? '/api/d1/provenance'+path : base.replace(/\/$/,'')+'/api/d1/provenance'+path;
}
export async function provenanceRequest(base:string,path:string,options?:RequestInit) {
  const response=await fetch(provenanceEndpoint(base,path),{...options,signal:options?.signal||AbortSignal.timeout(300_000)});
  if(!response.ok){
    const error=await response.json().catch(()=>null);
    throw new Error(typeof error?.detail==='string'?error.detail:'The provenance request failed.');
  }
  return response;
}


export async function latestCaseProvenance(base:string,caseId:string,signal?:AbortSignal) {
  const response=await provenanceRequest(base,'/cases/'+encodeURIComponent(caseId)+'/latest',{signal});
  return provenanceReportSchema.nullable().parse(await response.json());
}
