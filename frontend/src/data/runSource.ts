import type {Channel,Evidence,Finding} from '../model';
import {createRunId} from '../runs/retry';
import {transitionRun} from '../runs/runLifecycle';
import type {RunRecord,RunStatus} from '../runs/types';

export type CreateRunInput={evidence:Evidence;requestedChannels?:Channel[];configurationVersion?:string;now?:string;newId?:string};
export type RunSubscriber=(run:RunRecord)=>void;
export interface RunSource{listRuns(scope:string):RunRecord[];getRun(id:string):RunRecord|undefined;createRun(input:CreateRunInput):RunRecord;transition(id:string,status:RunStatus,now?:string):RunRecord;subscribe(id:string,callback:RunSubscriber):()=>void;add(run:RunRecord):RunRecord;replace(run:RunRecord):RunRecord}
export class MemoryRunSource implements RunSource{
 private records=new Map<string,RunRecord>();private listeners=new Map<string,Set<RunSubscriber>>();
 constructor(initial:readonly RunRecord[]=[]){initial.forEach(run=>this.records.set(run.run_id,run))}
 listRuns(scope:string){return [...this.records.values()].filter(run=>run.evidence_id===scope)}getRun(id:string){return this.records.get(id)}
 add(run:RunRecord){if(this.records.has(run.run_id))throw new Error(`Run ${run.run_id} already exists.`);this.records.set(run.run_id,run);this.emit(run);return run}
 replace(run:RunRecord){if(!this.records.has(run.run_id))throw new Error(`Unknown run ${run.run_id}.`);this.records.set(run.run_id,run);this.emit(run);return run}
 createRun({evidence,requestedChannels=['synthetic_media','tampering','integrity','provenance'],configurationVersion='dashboard-current',now=new Date().toISOString(),newId=createRunId()}:CreateRunInput){const run:RunRecord={schema_version:'1.1',run_id:newId,evidence_id:evidence.id,modality:evidence.type,execution_status:'failed',requested_at:now,started_at:null,completed_at:now,configuration:{name:'dashboard analysis',version:configurationVersion},configuration_version:configurationVersion,findings:[],coverage:null,artifacts:[],errors:[{code:'BACKEND_NOT_CONNECTED',message:'No analysis backend is connected; the request was not sent.',retryable:true}],fixture:false,attempt:1,retry_of:null,origin:'client',requested_channels:requestedChannels,status_reason:'backend_not_connected'};return this.add(run)}
 transition(id:string,status:RunStatus,now=new Date().toISOString()){const current=this.records.get(id);if(!current)throw new Error(`Unknown run ${id}.`);const next=transitionRun(current,status,now);this.records.set(id,next);this.emit(next);return next}
 subscribe(id:string,callback:RunSubscriber){const set=this.listeners.get(id)??new Set<RunSubscriber>();set.add(callback);this.listeners.set(id,set);return()=>{set.delete(callback)}}
 private emit(run:RunRecord){this.listeners.get(run.run_id)?.forEach(callback=>callback(run))}
}
export function restampFindings(findings:readonly Finding[],run:RunRecord):Finding[]{return findings.map((finding,index)=>({...finding,finding_id:`F-${run.run_id.slice(4)}${index.toString(16)}`,run_id:run.run_id,evidence_id:run.evidence_id,fixture:true}))}
