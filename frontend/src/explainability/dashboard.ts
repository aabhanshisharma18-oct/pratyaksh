import type {Evidence,Finding,Channel} from '../model';
import type {RunRecord} from '../runs/types';
import {classification,tone} from '../model';
import {scoreMeaning} from '../data/scoreMeaning';
import {locationChips} from '../findings/location';

export type ExplanationLevel='localized'|'traceable'|'limited';
export type ExplainedFinding={finding:Finding;evidence?:Evidence;run?:RunRecord;classification:string;tone:string;level:ExplanationLevel;levelLabel:string;locationLabel:string;scorePercent:number|null;scoreMeaning:string;basis:string[];unknowns:string[]};
const levelLabel:Record<ExplanationLevel,string>={localized:'Localized evidence',traceable:'Trace explanation',limited:'Limited explanation'};

function normalizedScore(finding:Finding):number|null{const score=finding.score;if(!score||score.value==null)return null;const[minimum,maximum]=score.range;if(!Number.isFinite(minimum)||!Number.isFinite(maximum)||maximum<=minimum)return null;return Math.max(0,Math.min(100,((score.value-minimum)/(maximum-minimum))*100))}
function coverageText(run?:RunRecord):string|null{if(!run?.coverage)return null;const{examined,planned,unexamined,rejected}=run.coverage;return `${examined} of ${planned} planned samples examined · ${unexamined} unexamined · ${rejected} rejected`}

export function explainFinding(finding:Finding,evidence?:Evidence,run?:RunRecord):ExplainedFinding{
 const locations=locationChips(finding),complete=finding.execution_status==='completed';
 const level:ExplanationLevel=locations.length?'localized':complete&&(finding.score||finding.details)?'traceable':'limited';
 const coverage=coverageText(run);
 const basis=[`Method: ${finding.method} (${finding.method_version})`,`Examined scope: ${finding.scope}`,...(finding.score?.value!=null?[`Model signal: ${finding.score.value} on a ${finding.score.range[0]}–${finding.score.range[1]} range; positive class is ${finding.score.positive_class}`]:[]),...(locations.length?[`Location: ${locations.map(item=>item.label).join(', ')}`]:[]),...(coverage?[`Coverage: ${coverage}`]:[]),...(finding.support_refs.length?[`${finding.support_refs.length} supporting artifact reference${finding.support_refs.length===1?'':'s'} recorded`]:[])];
 const unknowns=[...finding.limitations,...(!finding.score?['No numerical model signal was recorded for this finding.']:[]),...(finding.score?.calibration_status.toLowerCase().includes('not calibrated')?['The model signal is not calibrated as a probability.']:[]),...(!locations.length?['No pixel region or time segment was localized for this finding.']:[]),...(run?.coverage&&run.coverage.unexamined>0?[`${run.coverage.unexamined} planned sample${run.coverage.unexamined===1?' was':'s were'} not examined.`]:[])];
 return{finding,evidence,run,classification:classification(finding),tone:tone(finding),level,levelLabel:levelLabel[level],locationLabel:locations.map(item=>item.label).join(', ')||'Whole-file or unspecified scope',scorePercent:normalizedScore(finding),scoreMeaning:scoreMeaning(finding),basis,unknowns:[...new Set(unknowns)]};
}

export type DashboardSummary={total:number;completed:number;indicators:number;inconclusive:number;unavailable:number;localized:number;channels:Record<Channel,number>};
export function summarizeExplainability(findings:Finding[]):DashboardSummary{const channels:Record<Channel,number>={synthetic_media:0,tampering:0,integrity:0,provenance:0};findings.forEach(item=>{channels[item.category]+=1});return{total:findings.length,completed:findings.filter(item=>item.execution_status==='completed').length,indicators:findings.filter(item=>item.execution_status==='completed'&&item.result==='indicators_detected').length,inconclusive:findings.filter(item=>item.execution_status==='completed'&&item.result==='inconclusive').length,unavailable:findings.filter(item=>['failed','unsupported','cancelled'].includes(item.execution_status)).length,localized:findings.filter(item=>locationChips(item).length>0).length,channels}}
