import {channels,classification,type Finding} from '../model';
import type {SavedReport} from './api';

export type ReportData=SavedReport['snapshot'];
export const coverageStates=['completed','partial','failed','unsupported','running','queued','cancelled','not_applicable','not_assessed'] as const;
export type CoverageState=typeof coverageStates[number];
export function cellState(findings:Finding[]):CoverageState{
 if(!findings.length)return 'not_assessed';
 const states=findings.map(f=>f.execution_status);
 if(states.includes('running'))return 'running';
 if(states.includes('queued'))return 'queued';
 if(states.every(s=>s==='completed'))return 'completed';
 if(states.includes('completed'))return 'partial';
 if(states.includes('failed'))return 'failed';
 if(states.includes('unsupported'))return 'unsupported';
 if(states.includes('cancelled'))return 'cancelled';
 return 'not_applicable';
}
export function reportVisualModel(report:ReportData){
 const findings=report.findings.map(record=>record.finding);
 const matrix=report.evidence.map(evidence=>({evidence,cells:channels.map(channel=>{
  const matches=findings.filter(f=>f.evidence_id===evidence.evidence_id&&f.category===channel.key);
  return {channel:channel.key,state:cellState(matches),findings:matches};
 })}));
 const counts=Object.fromEntries(coverageStates.map(status=>[status,0])) as Record<CoverageState,number>;
 matrix.forEach(row=>row.cells.forEach(cell=>counts[cell.state]++));
 const channelSummaries=channels.map(channel=>{
  const matches=findings.filter(f=>f.category===channel.key);
  const labels=new Map<string,number>();
  matches.forEach(f=>{const label=classification(f);labels.set(label,(labels.get(label)??0)+1)});
  return {...channel,count:matches.length,labels:[...labels],missing:matrix.filter(row=>row.cells.find(c=>c.channel===channel.key)?.state==='not_assessed').length};
 });
 return {matrix,counts,total:matrix.length*channels.length,channelSummaries};
}

export function scoreGroups(report:ReportData,evidenceId:string){
 const groups=new Map<string,{id:string;method:string;runId:string;positiveClass:string;calibration:string;range:[number,number];points:{id:string;value:number;time:number|null}[]}>();
 for(const {finding:f} of report.findings){
  if(f.evidence_id!==evidenceId||f.execution_status!=='completed'||!f.score||f.score.value===null)continue;
  const {value,range}=f.score;
  if(!Number.isFinite(value)||!range.every(Number.isFinite)||range[1]<=range[0]||value<range[0]||value>range[1])continue;
  const key=JSON.stringify([f.run_id,f.method,f.method_version,f.score.positive_class,range,f.score.calibration_status]);
  if(!groups.has(key))groups.set(key,{id:key,method:f.method,runId:f.run_id,positiveClass:f.score.positive_class,calibration:f.score.calibration_status,range,points:[]});
  const location=f.location;
  const time=location?.timestamp_ms??location?.frame_timestamp_ms??location?.start_ms;
  groups.get(key)!.points.push({id:f.finding_id,value,time:typeof time==='number'&&Number.isFinite(time)&&time>=0?time:null});
 }
 return [...groups.values()];
}

export function reportMilestones(report:ReportData){
 const events=report.audit_summary?.events??[];
 const rows:{id:string;label:string;time:string;actor:string}[]=[];
 const add=(label:string,event:typeof events[number]|undefined)=>{if(event)rows.push({id:event.id,label,time:event.created_at,actor:event.actor})};
 add('Case created',events.find(e=>e.type==='case.created'));
 add('Evidence registered',events.find(e=>e.type==='evidence.registered'));
 add('Run started',events.find(e=>e.type==='run.started'));
 add('Run finished',[...events].reverse().find(e=>['run.completed','run.partial','run.failed'].includes(e.type)));
 rows.push({id:report.report_id,label:'Report prepared',time:report.prepared_at??report.generated_at,actor:report.preparer});
 const latest=report.review_history?.at(-1);
 if(latest)rows.push({id:report.report_id+'-review',label:'Report reviewed',time:latest.reviewed_at,actor:latest.reviewer});
 return rows.filter(row=>Number.isFinite(Date.parse(row.time))).sort((a,b)=>Date.parse(a.time)-Date.parse(b.time));
}
