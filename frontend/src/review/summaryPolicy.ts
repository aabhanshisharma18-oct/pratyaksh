import {classification,type Finding,type Note} from '../model';

export type SummaryReference={evidenceId:string;findingId:string;location:string;method:string;limitation:string};
export type SummaryStatement={id:string;text:string;reference:SummaryReference};
export type SummaryEdit={statementId:string;author:string;at:string;before:string;after:string};

export const forbiddenSummaryPhrases=[/\bdefinitely fake\b/i,/\bauthentic\b/i,/\bproven manipulated\b/i];

export function findingLocation(finding:Finding):string{
 const location=finding.location;
 if(!location)return 'whole examined scope';
 if(location.start_ms!=null||location.end_ms!=null){const start=((location.start_ms??0)/1000).toFixed(2),end=((location.end_ms??location.start_ms??0)/1000).toFixed(2);return `${start}s–${end}s`}
 if(location.timestamp_ms!=null)return `${(location.timestamp_ms/1000).toFixed(2)}s`;
 if(location.frame_timestamp_ms!=null)return `${(location.frame_timestamp_ms/1000).toFixed(2)}s`;
 if(location.label)return location.label;
 if(location.x!=null)return 'recorded image region';
 return 'recorded location';
}

export function summaryTextIsAllowed(text:string):boolean{return text.trim().length>0&&!forbiddenSummaryPhrases.some(pattern=>pattern.test(text))}

export function buildReferencedSummary(findings:Finding[]):SummaryStatement[]{
 return findings.map(finding=>{
  const location=findingLocation(finding);
  const calibration=finding.score?.calibration_status?` Calibration: ${finding.score.calibration_status}.`:'';
  const limitation=finding.limitations[0]||'This finding does not establish the authenticity of the media.';
  const text=`${classification(finding)} was recorded for ${finding.evidence_id} at ${location} using ${finding.method} ${finding.method_version}.${calibration} ${limitation}`;
  return {id:`summary-${finding.finding_id}`,text:summaryTextIsAllowed(text)?text:`A bounded technical finding was recorded for ${finding.evidence_id} at ${location} using ${finding.method} ${finding.method_version}. ${limitation}`,reference:{evidenceId:finding.evidence_id,findingId:finding.finding_id,location,method:`${finding.method} ${finding.method_version}`,limitation}};
 });
}

export function validateSummaryReferences(statements:SummaryStatement[],findings:Finding[]):SummaryStatement[]{
 const byId=new Map(findings.map(finding=>[finding.finding_id,finding]));
 return statements.filter(statement=>{
  const finding=byId.get(statement.reference.findingId);
  return Boolean(finding&&finding.evidence_id===statement.reference.evidenceId&&statement.reference.method===`${finding.method} ${finding.method_version}`&&statement.reference.limitation&&summaryTextIsAllowed(statement.text));
 });
}

export function reportGate(findings:Finding[],notes:Note[],summaryApproved:boolean):{ready:boolean;unreviewed:string[]}{
 const required=findings.filter(finding=>finding.execution_status==='completed');
 const reviewed=new Set(notes.map(note=>note.findingId));
 const unreviewed=required.filter(finding=>!reviewed.has(finding.finding_id)).map(finding=>finding.finding_id);
 return {ready:summaryApproved&&required.length>0&&unreviewed.length===0,unreviewed};
}
