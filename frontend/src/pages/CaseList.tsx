import React,{useMemo,useState} from 'react';
import {ArrowUpRight,FolderOpen,Plus,Search} from 'lucide-react';
import {CaseRecord,Evidence,Finding} from '../model';
import {CaseSort,filterAndSortCases} from '../data/caseSource';
import {selectProcessingSummary} from '../selectors/processing';
import {useI18n} from '../i18n';

type Props={cases:CaseRecord[];evidenceFor:(caseId:string)=>Evidence[];findingsFor:(caseId:string)=>Finding[];onOpen:(caseId:string)=>void;onCreate:()=>void};
export function CaseList({cases,evidenceFor,findingsFor,onOpen,onCreate}:Props){
  const {t}=useI18n();
  const [query,setQuery]=useState('');
  const [status,setStatus]=useState('All');
  const [sort,setSort]=useState<CaseSort>('newest');
  const statuses=useMemo(()=>Array.from(new Set(cases.map(item=>item.status))),[cases]);
  const visible=useMemo(()=>filterAndSortCases(cases,query,status,sort),[cases,query,status,sort]);
  return <section className="cases-page"><div className="page-heading standalone"><div><div className="eyebrow">WORKSPACE</div><h1>{t('Case list')}</h1><p>Open an investigation or create a new browser-local case.</p></div><button className="button primary" onClick={onCreate}><Plus size={15}/>{t('New case')}</button></div>
    {cases.length?<><div className="case-list-tools"><label><Search size={15}/><input aria-label={t('Search cases')} placeholder={t('Search cases')} value={query} onChange={event=>setQuery(event.target.value)}/></label><select aria-label={t('All statuses')} value={status} onChange={event=>setStatus(event.target.value)}><option value="All">{t('All statuses')}</option>{statuses.map(value=><option key={value}>{value}</option>)}</select><select aria-label="Sort cases" value={sort} onChange={event=>setSort(event.target.value as CaseSort)}><option value="newest">{t('Newest first')}</option><option value="oldest">{t('Oldest first')}</option><option value="title">{t('Title')}</option></select></div><div className="case-list">{visible.map(item=>{const evidence=evidenceFor(item.id);const summary=selectProcessingSummary(evidence,findingsFor(item.id));const active=summary.channels.flatMap(channel=>[channel.counts.running,channel.counts.queued]).reduce((sum,value)=>sum+value,0);const failed=summary.channels.reduce((sum,channel)=>sum+channel.counts.failed,0);return <article className="case-card" key={item.id}><div className="case-card-heading"><span className="case-folder"><FolderOpen size={19}/></span><div><span className="mono">{item.id}</span><h2>{item.title}</h2></div><span className="badge neutral"><i className="badge-dot"/>{item.status}</span></div><p>{item.description||'No case description recorded.'}</p><dl><div><dt>{t('Created')}</dt><dd>{item.created}</dd></div><div><dt>{t('Evidence items')}</dt><dd>{evidence.length}</dd></div><div><dt>{t('Processing status')}</dt><dd>{active?`${active} active`:failed?`${failed} failed`:summary.lastRunId?'Completed fixture records':t('Not examined')}</dd></div></dl><button className="button secondary" onClick={()=>onOpen(item.id)}>{t('Open case')}<ArrowUpRight size={14}/></button></article>})}</div>{!visible.length&&<div className="empty"><Search size={28}/><h3>No matching cases</h3><p>Try another search or status filter.</p></div>}</>:<div className="empty large"><FolderOpen size={36}/><h2>{t('No cases yet')}</h2><p>Create a browser-local investigation workspace to begin.</p><button className="button primary" onClick={onCreate}><Plus size={15}/>{t('Create your first case')}</button></div>}
  </section>;
}
