import {z} from 'zod';
import {routeFor} from '../app/routing';

const sourceSchema=z.object({
 source_id:z.string(),kind:z.enum(['finding','relationship','run','evidence']),
 evidence_ids:z.array(z.string()).min(1),media_types:z.array(z.string()),observation:z.string(),
 finding_id:z.string().optional(),run_id:z.string().nullish(),analysis_id:z.string().optional(),relationship_id:z.string().optional(),
 execution_status:z.string().nullish(),result:z.string().nullish(),method:z.string().optional(),scope:z.string().optional(),
 limitations:z.array(z.string()).default([]),
}).passthrough();
const itemSchema=z.object({text:z.string(),basis:z.string(),source_ids:z.array(z.string()).min(1)});
export const caseBriefingSchema=z.object({
 case_id:z.string(),snapshot_sha256:z.string(),generated_at:z.string(),model:z.string(),cached:z.boolean(),
 key_findings:z.array(itemSchema),open_questions:z.array(itemSchema),next_steps:z.array(itemSchema),
 cautions:z.array(z.object({text:z.string(),source_ids:z.array(z.string()).min(1)})),sources:z.array(sourceSchema),
}).superRefine((briefing,context)=>{
 const ids=new Set(briefing.sources.map(source=>source.source_id));
 for(const item of [...briefing.key_findings,...briefing.open_questions,...briefing.next_steps,...briefing.cautions])
  if(item.source_ids.some(id=>!ids.has(id)))context.addIssue({code:'custom',message:'Unknown case citation.'});
});
export type CaseBriefing=z.infer<typeof caseBriefingSchema>;
export type BriefingSource=z.infer<typeof sourceSchema>;

export function briefingSourceRoute(caseId:string,source:BriefingSource):string{
 if(source.kind==='relationship'&&source.analysis_id&&source.relationship_id){
  const params=new URLSearchParams({analysis:source.analysis_id,relationship:source.relationship_id});
  return `/cases/${encodeURIComponent(caseId)}/provenance?${params}`;
 }
 return routeFor('Workbench',caseId,source.evidence_ids[0],'Viewer',{findingId:source.finding_id,runId:source.run_id});
}

export async function explainCase(baseUrl:string,caseId:string,signal:AbortSignal,fetchImpl:typeof fetch=fetch):Promise<CaseBriefing>{
 const response=await fetchImpl(baseUrl.replace(/\/$/,'')+'/api/cases/'+encodeURIComponent(caseId)+'/briefing',{
  method:'POST',signal,headers:{Accept:'application/json'},
 });
 const body:unknown=await response.json().catch(()=>null);
 if(!response.ok){
  const detail=body&&typeof body==='object'&&'detail' in body?body.detail:null;
  throw new Error(typeof detail==='string'?detail:'The case explanation is unavailable. Your saved findings are still available below.');
 }
 const parsed=caseBriefingSchema.safeParse(body);
 if(!parsed.success||parsed.data.case_id!==caseId)throw new Error('The explanation could not be matched to this case.');
 return parsed.data;
}
