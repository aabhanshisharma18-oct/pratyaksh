import {ChevronDown,ChevronUp,Eye,RotateCcw,SlidersHorizontal} from 'lucide-react';
import {useMemo,useState} from 'react';
import {useI18n} from '../../i18n';
import {channels} from '../../model';
import {canRetry,type RetryContext} from '../../runs/retry';
import {deriveSteps,durationMs,formatDuration,newestFirst} from '../../runs/presentation';
import {configurationVersion,runAttempt,runOrigin,type RunRecord} from '../../runs/types';
import {formatReceived} from '../EvidenceTable';
import {RunDetailsDrawer} from './RunDetailsDrawer';
import {RunStatusBadge} from './RunStatusBadge';

export function RunHistoryPanel({runs,retryContext,onRetry,onViewFindings}:{runs:RunRecord[];retryContext:Omit<RetryContext,'runs'>;onRetry:(run:RunRecord)=>void;onViewFindings:(id:string)=>void}){
  const {language,t}=useI18n(),[open,setOpen]=useState(true),[details,setDetails]=useState<RunRecord|null>(null);
  const ordered=useMemo(()=>newestFirst(runs),[runs]),latest=ordered[0];
  return <section className="run-history">
    <button className="job-toggle" onClick={()=>setOpen(value=>!value)} aria-expanded={open}><SlidersHorizontal size={15}/><strong>{t('run.analysisRuns')}</strong>{latest?<><RunStatusBadge run={latest} compact/><span>{latest.run_id}</span></>:<span>{t('run.noRunRecorded')}</span>}{open?<ChevronUp size={15}/>:<ChevronDown size={15}/>}</button>
    {open&&<div className="run-history-body">{ordered.length?ordered.map(run=>{const eligibility=canRetry(run,{...retryContext,runs}),steps=deriveSteps(run);return <article className="run-row" key={run.run_id}>
      <div className="run-row-head"><div><strong className="mono">{run.run_id}</strong><span>{t('run.attemptLabel',{attempt:runAttempt(run)})} · {runOrigin(run)}{run.simulated?` · ${t('run.simulatedFixture').toUpperCase()}`:''}</span>{run.retry_of&&<button className="text-button" onClick={()=>document.getElementById(`run-${run.retry_of}`)?.scrollIntoView({behavior:'smooth'})}>{t('run.retryOf',{runId:run.retry_of})}</button>}</div><RunStatusBadge run={run}/></div>
      <div className="run-meta" id={`run-${run.run_id}`}><span>{t('run.requestedAt',{date:formatReceived(run.requested_at,language)})}</span><span>{t('run.startedAt',{date:run.started_at?formatReceived(run.started_at,language):'—'})}</span><span>{t('run.completedOn',{date:run.completed_at?formatReceived(run.completed_at,language):'—'})}</span><span>{t('run.duration',{duration:formatDuration(durationMs(run))})}</span><span>{t('run.config',{version:configurationVersion(run)})}</span></div>
      <div className="run-steps">{channels.map(channel=><span className={`run-step ${steps[channel.key]}`} key={channel.key}><i/>{t(channel.name)}<small>{steps[channel.key].replace('_',' ')}</small></span>)}</div>
      <p className="run-coverage">{run.coverage?t('run.plannedCoverage',{examined:run.coverage.examined,planned:run.coverage.planned,unexamined:run.coverage.unexamined}):t('run.coverageNotReported')}</p>
      {run.errors.at(-1)&&<p className="run-error"><strong>{run.errors.at(-1)!.code}</strong>: {run.errors.at(-1)!.message} · {t('run.retryable')} {String(run.errors.at(-1)!.retryable)}</p>}
      <div className="run-actions"><button className="button subtle" disabled={!run.findings.length} onClick={()=>onViewFindings(run.run_id)}><Eye size={14}/>{t('run.viewFindings')}</button><button className="button subtle" onClick={()=>setDetails(run)}>{t('common.details')}</button><button className="button secondary" aria-disabled={!eligibility.allowed} disabled={!eligibility.allowed} onClick={()=>onRetry(run)}><RotateCcw size={14}/>{t('run.retryNew')}</button></div>
      {!eligibility.allowed&&<p className="retry-reason">{t(eligibility.reason)}</p>}
    </article>}):<div className="empty compact"><h3>{t('run.noRuns')}</h3><p>{t('run.noRunsDescription')}</p></div>}</div>}
    {details&&<RunDetailsDrawer run={details} onClose={()=>setDetails(null)}/>}
  </section>;
}
