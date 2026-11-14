import {Channel,channels,Evidence,Finding} from '../model';
import type {RunRecord,RunStatus} from '../runs/types';

export type ExecutionStatus=Finding['execution_status'];
export type ChannelCounts=Record<ExecutionStatus,number>&{not_examined:number};
export type ProcessingChannelSummary={channel:Channel;label:string;counts:ChannelCounts};
export type ProcessingSummaryData={channels:ProcessingChannelSummary[];lastRunId:string|null;fixture:boolean;runs:Record<RunStatus,number>};

const emptyCounts=():ChannelCounts=>({queued:0,running:0,completed:0,failed:0,unsupported:0,not_applicable:0,cancelled:0,not_examined:0});

export function selectProcessingSummary(evidence:Evidence[],findings:Finding[],runs:readonly RunRecord[]=[]):ProcessingSummaryData{
  const ids=new Set(evidence.map(item=>item.id));
  const relevant=findings.filter(finding=>ids.has(finding.evidence_id));
  const summaries=channels.map(({key,name})=>{
    const counts=emptyCounts();
    for(const item of evidence){
      const matches=relevant.filter(finding=>finding.evidence_id===item.id&&finding.category===key);
      if(!matches.length)counts.not_examined+=1;
      else matches.forEach(finding=>{counts[finding.execution_status]+=1});
    }
    return {channel:key,label:name,counts};
  });
  return {
    channels:summaries,
    lastRunId:runs.filter(run=>ids.has(run.evidence_id)).sort((a,b)=>Date.parse(b.requested_at)-Date.parse(a.requested_at))[0]?.run_id??null,
    fixture:relevant.some(item=>item.fixture),
    runs:runs.filter(run=>ids.has(run.evidence_id)).reduce((counts,run)=>{counts[run.execution_status]+=1;return counts},{queued:0,running:0,completed:0,partial:0,failed:0,unsupported:0,cancelled:0} as Record<RunStatus,number>),
  };
}
