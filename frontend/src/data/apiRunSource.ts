import {z} from 'zod';
import {findingSchema,type Evidence} from '../model';
import {runStatuses,type RunRecord} from '../runs/types';

const coverageSchema=z.object({
 planned:z.number().int().nonnegative(),examined:z.number().int().nonnegative(),rejected:z.number().int().nonnegative(),unexamined:z.number().int().nonnegative(),
 percent:z.number().min(0).max(100).optional(),duration_ms:z.number().int().nonnegative().optional(),strategy:z.string().nullable().optional(),sampling_interval_ms:z.number().int().positive().optional(),
 samples:z.array(z.object({index:z.number().int().nonnegative(),timestamp_ms:z.number().int().nonnegative().nullable().optional(),status:z.enum(['examined','rejected','unexamined']),reason:z.string().nullable()})),
});
const runSchema=z.object({
 schema_version:z.literal('1.1'),run_id:z.string(),case_id:z.string().optional(),evidence_id:z.string(),modality:z.enum(['image','audio','video']),execution_status:z.enum(runStatuses),
 requested_at:z.string(),started_at:z.string().nullable(),completed_at:z.string().nullable(),retry_of:z.string().nullable(),retry_children:z.array(z.string()).default([]),attempt:z.number().int().positive(),
 requested_checks:z.array(z.string()).default([]),configuration:z.object({name:z.string(),version:z.string()}),configuration_version:z.string().optional(),findings:z.array(findingSchema),coverage:coverageSchema.nullable(),
 artifacts:z.array(z.object({artifact_id:z.string(),kind:z.string()})).default([]),errors:z.array(z.object({code:z.string(),message:z.string(),retryable:z.boolean()})).default([]),fixture:z.literal(false),origin:z.literal('server'),
});
const listSchema=z.object({items:z.array(runSchema),total:z.number().int().nonnegative()});
const terminal=new Set(['completed','partial','failed','unsupported','cancelled']);

export class RunApiError extends Error {
 constructor(message:string,readonly status:number){super(message)}
}

export class ApiRunSource{
 constructor(private baseUrl:string,private fetchImpl:typeof fetch=globalThis.fetch.bind(globalThis) as typeof fetch){}
 private url(path:string){return this.baseUrl.replace(/\/$/,'')+path}
 private async request(path:string,init?:RequestInit){const response=await this.fetchImpl(this.url(path),init);const body:unknown=await response.json().catch(()=>null);if(!response.ok)throw new RunApiError(typeof (body as {detail?:unknown})?.detail==='string'?(body as {detail:string}).detail:`Run API returned HTTP ${response.status}.`,response.status);return body}
 async listRuns(evidenceId:string,caseId:string){return listSchema.parse(await this.request(`/api/evidence/${encodeURIComponent(evidenceId)}/runs?case_id=${encodeURIComponent(caseId)}`)).items as RunRecord[]}
 async getRun(runId:string,signal?:AbortSignal){return runSchema.parse(await this.request(`/api/runs/${encodeURIComponent(runId)}`,{signal})) as RunRecord}
 async createRun(evidence:Evidence){
  if(!evidence.caseId)throw new Error('A persistent run requires a case ID.');
  const form=new FormData();
  form.set('case_id',evidence.caseId);
  if(!evidence.preserved){
    if(!evidence.source)throw new Error('Re-add the evidence file before requesting its first analysis run.');
    const media=await this.fetchImpl(evidence.source);
    if(!media.ok)throw new Error('The evidence file could not be read.');
    form.set('file',await media.blob(),evidence.name);
  }
  return runSchema.parse(await this.request(`/api/evidence/${encodeURIComponent(evidence.id)}/runs`,{method:'POST',body:form})) as RunRecord;
 }
 async retryRun(run:RunRecord,caseId:string){const form=new FormData();form.set('case_id',caseId);form.set('retry_of_run_id',run.run_id);return runSchema.parse(await this.request(`/api/evidence/${encodeURIComponent(run.evidence_id)}/runs`,{method:'POST',body:form})) as RunRecord}
 subscribe(runId:string,callback:(run:RunRecord)=>void,onError:(error:Error)=>void,intervalMs=1000){
  const controller=new AbortController();
  let timer:number|undefined;
  let failures=0;
  const poll=async()=>{
   const request=new AbortController();
   const cancel=()=>request.abort();
   controller.signal.addEventListener('abort',cancel,{once:true});
   const timeout=window.setTimeout(cancel,10000);
   let run:RunRecord;
   try{
    run=await this.getRun(runId,request.signal);
   }catch(error){
    if(controller.signal.aborted)return;
    const permanent=error instanceof z.ZodError ||
      (error instanceof RunApiError && error.status>=400 && error.status<500 && ![408,429].includes(error.status));
    if(permanent||++failures>=3){
     onError(error instanceof Error && error.name!=='AbortError'?error:new Error('Run status request timed out.'));
    }else timer=window.setTimeout(poll,intervalMs);
    return;
   }finally{
    window.clearTimeout(timeout);
    controller.signal.removeEventListener('abort',cancel);
   }
   if(controller.signal.aborted)return;
   failures=0;
   callback(run);
   if(!terminal.has(run.execution_status)&&!controller.signal.aborted)timer=window.setTimeout(poll,intervalMs);
  };
  void poll();
  return()=>{controller.abort();if(timer!==undefined)window.clearTimeout(timer)};
 }
}
