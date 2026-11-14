import {useEffect,useState} from 'react';
import {Clock3,ClipboardCheck,FileCheck2} from 'lucide-react';
import {translate} from '../i18n';
import {createReviewApi} from '../data/reviewApi';
import {reportApi} from '../reports/api';
import type {CaseRecord} from '../model';

type Status='pending'|'review'|'reported';
export function caseOverviewStatus(hasFindings:boolean,hasReport:boolean):Status{
 return hasReport?'reported':hasFindings?'review':'pending';
}
type Props={cases:CaseRecord[];baseUrl?:string;hasFindings:(id:string)=>boolean;hasReport:(id:string)=>boolean};
export function CaseStatusOverview({cases,baseUrl,hasFindings,hasReport}:Props){
 const [remote,setRemote]=useState<{key:string;values:Status[];failed:number}|null>(null);
 const key=cases.map(item=>`${item.id}:${item.lastActivityAt??''}`).join('|');
 useEffect(()=>{
  if(!baseUrl)return;
  const controller=new AbortController();
  const ids=cases.map(item=>item.id);
  Promise.all(ids.map(async id=>{
   try{const [findings,reports]=await Promise.all([createReviewApi(baseUrl).listFindings(id,controller.signal),reportApi(baseUrl).list(id,controller.signal)]);return caseOverviewStatus(findings.length>0,reports.length>0)}catch{return null}
  })).then(values=>{if(!controller.signal.aborted)setRemote({key,values:values.filter((value):value is Status=>value!==null),failed:values.filter(value=>value===null).length})});
  return()=>controller.abort();
 },[baseUrl,key]);
 const loaded=!baseUrl||remote?.key===key;
 const values=baseUrl?(remote?.key===key?remote.values:[]):cases.map(item=>caseOverviewStatus(hasFindings(item.id),hasReport(item.id)));
 const groups=[{id:'pending',label:'Pending',icon:Clock3},{id:'review',label:'Needs review',icon:ClipboardCheck},{id:'reported',label:'Report saved',icon:FileCheck2}] as const;
 return <section className="case-status-overview" aria-label={translate('Case status overview')} aria-busy={!loaded}>
  {groups.map(group=>{const count=values.filter(value=>value===group.id).length;return <div key={group.id} className={`case-status-summary ${group.id}`}><group.icon size={20}/><span>{translate(group.label)}</span><strong>{loaded?count:'—'}</strong><span className="case-status-meter" aria-hidden="true"><i style={{width:`${cases.length?count/cases.length*100:0}%`}}/></span></div>})}
  {baseUrl&&remote?.key===key&&remote.failed>0&&<p role="status">{translate('Some case statuses could not be loaded. Counts exclude those cases.')}</p>}
 </section>;
}
