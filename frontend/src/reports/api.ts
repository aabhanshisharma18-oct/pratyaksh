import type {ReportSection} from './sections';
import {z} from 'zod';
import {apiCaseDetailSchema, apiEvidenceSchema, findingSchema} from '../model';

const digest=z.string().regex(/^[a-f0-9]{64}$/);
export const revisionSchema=z.object({report_id:z.string(),revision:z.number().int().positive(),sha256:digest});
export const savedReportSchema=z.object({sha256:digest,snapshot:z.object({
 schema_version:z.enum(['d5.1','d5.2','d5.3','d5.4','d5.5','d5.6','d5.7']),report_id:z.string(),revision:z.number().int().positive(),
 generated_at:z.string(),preparer:z.string(),preparer_verified:z.literal(false),
 prepared_at:z.string().optional(),parent_report_id:z.string().optional(),parent_report_sha256:digest.optional(),
 review_history:z.array(z.object({reviewer:z.string(),reviewer_verified:z.literal(false),status:z.enum(['reviewed','questioned']),note:z.string(),reviewed_at:z.string(),source_report_id:z.string(),source_report_sha256:digest})).optional(),
 package_policy:z.object({include_artifacts_requested:z.boolean(),original_media_included:z.literal(false),verified_artifact_count:z.number().int().nonnegative()}).optional(),
 source_references:z.object({runs:z.array(z.object({run_id:z.string(),status:z.enum(['recorded','not_found','not_available','case_or_evidence_mismatch']),record:z.record(z.string(),z.unknown()).nullable()})),artifacts:z.array(z.object({reference:z.string(),finding_id:z.string(),run_id:z.string(),evidence_id:z.string(),status:z.enum(['metadata_recorded','ambiguous','unresolved','verified']),metadata:z.record(z.string(),z.unknown()).nullable(),bytes_verified:z.boolean(),bytes_included:z.boolean(),verification:z.string().optional(),zip_path:z.string().optional()})),limitations:z.array(z.string())}).optional(),
 analyst_context:z.object({questions:z.string(),next_steps:z.string(),author:z.string(),author_verified:z.literal(false)}).optional(),
 audit_summary:z.object({scope:z.literal('case-wide'),captured_at:z.string(),included_count:z.number().int(),counts_by_type:z.record(z.string(),z.number().int()),truncated:z.boolean(),limit:z.number().int(),limitations:z.array(z.string()),events:z.array(z.object({id:z.string(),type:z.string(),actor:z.string(),created_at:z.string(),summary:z.string(),evidence_id:z.string().nullable(),run_id:z.string().nullable()}))}).optional(),
 sections:z.array(z.enum(['methods','evidence','findings','coverage','notes','limitations'])).optional(),
 run_selection:z.object({mode:z.enum(['selected','all_registered']),run_ids:z.array(z.string()),excluded_finding_count:z.number().int().nonnegative()}).optional(),
 case:apiCaseDetailSchema,evidence:z.array(apiEvidenceSchema),
 findings:z.array(z.object({finding_id:z.string(),finding_sha256:digest,finding:findingSchema})),
 review_notes:z.record(z.string(),z.array(z.object({note_id:z.string(),text:z.string(),status:z.string(),author:z.string(),created_at:z.string()}))),
 coverage:z.array(z.object({evidence_id:z.string(),category:z.string(),finding_ids:z.array(z.string()),status:z.enum(['recorded','not_assessed'])})),
 fixture:z.boolean(),review_status:z.enum(['unreviewed','reviewed','questioned']),limitations:z.array(z.string()),
}).superRefine((snapshot,context)=>{
 for(const artifact of snapshot.source_references?.artifacts??[]){
  if(artifact.bytes_included||artifact.bytes_verified||artifact.status==='verified'){
   const hash=artifact.metadata?.sha256;
   if(artifact.status!=='verified'||!artifact.bytes_verified||!artifact.bytes_included||
      typeof hash!=='string'||!/^[a-f0-9]{64}$/.test(hash)||artifact.zip_path!==`artifacts/${hash}.bin`){
    context.addIssue({code:'custom',message:'Verified artifact flags require a matching hash and ZIP path'});
   }
  }
 }
 if(snapshot.review_status==='unreviewed')return;
 const latest=snapshot.review_history?.at(-1);
 if(!latest||latest.status!==snapshot.review_status||!snapshot.prepared_at||
    latest.source_report_id!==snapshot.parent_report_id||latest.source_report_sha256!==snapshot.parent_report_sha256){
  context.addIssue({code:'custom',message:'Reviewed reports require matching source and reviewer history'});
 }
})});
export const runOptionSchema=z.object({run_id:z.string(),status:z.string(),selectable:z.boolean(),status_source:z.enum(['run_record','registered_findings']),finding_count:z.number().int(),evidence_ids:z.array(z.string())});
export type RunOption=z.infer<typeof runOptionSchema>;
export type SavedReport=z.infer<typeof savedReportSchema>;
export type ReportRevision=z.infer<typeof revisionSchema>;

export function reportApi(baseUrl:string){
 const root=baseUrl.replace(/\/$/,'');
 async function request(path:string,init?:RequestInit){
  const response=await fetch(root+'/api'+path,{cache:'no-store',...init});
  if(!response.ok){
   let message=`Report request failed (${response.status})`;
   try{const body=await response.json();if(typeof body.detail==='string')message=body.detail}catch{}
   throw new Error(message);
  }
  return response;
 }
 return {
  async list(caseId:string,signal?:AbortSignal){return z.object({items:z.array(revisionSchema)}).parse(await (await request(`/cases/${encodeURIComponent(caseId)}/reports`,{signal})).json()).items},
  async get(id:string,signal?:AbortSignal){return savedReportSchema.parse(await (await request(`/reports/${encodeURIComponent(id)}`,{signal})).json())},
  async runOptions(caseId:string,signal?:AbortSignal){return z.object({items:z.array(runOptionSchema)}).parse(await (await request(`/cases/${encodeURIComponent(caseId)}/reports/run-options`,{signal})).json()).items},
  async save(caseId:string,preparer:string,runIds?:string[],sections?:ReportSection[],context?:{questions:string;next_steps:string;include_artifacts?:boolean}){return savedReportSchema.parse(await (await request(`/cases/${encodeURIComponent(caseId)}/reports`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preparer,...(runIds!==undefined?{run_ids:runIds}:{}),...(sections!==undefined?{sections}:{}),...(context??{})})})).json())},
  async review(id:string,reviewer:string,status:'reviewed'|'questioned',note:string){return savedReportSchema.parse(await (await request(`/reports/${encodeURIComponent(id)}/reviews`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reviewer,status,note})})).json())},
  async download(id:string,format:'json'|'zip'){
   const response=await request(`/reports/${encodeURIComponent(id)}/export?format=${format}`);
   const url=URL.createObjectURL(await response.blob());
   const link=document.createElement('a');link.href=url;link.download=`${id.replace(/[^a-zA-Z0-9-]/g,'_')}.${format}`;link.click();
   setTimeout(()=>URL.revokeObjectURL(url),1000);
  },
 };
}
