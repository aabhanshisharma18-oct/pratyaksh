import {Download,X} from 'lucide-react';
import {useI18n} from '../../i18n';
import type {RunRecord} from '../../runs/types';
import {configurationVersion,requestedChannels,runAttempt,runOrigin} from '../../runs/types';
import {formatReceived} from '../EvidenceTable';

export function RunDetailsDrawer({run,onClose}:{run:RunRecord;onClose:()=>void}){
  const {language,t}=useI18n();
  const download=()=>{const blob=new Blob([JSON.stringify(run,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=`${run.run_id}.json`;anchor.click();URL.revokeObjectURL(url)};
  const samples=run.coverage?.samples??[];
  return <div className="run-drawer-backdrop" role="presentation" onMouseDown={event=>{if(event.currentTarget===event.target)onClose()}}><section className="run-drawer" role="dialog" aria-modal="true" aria-labelledby="run-details-title">
    <header><div><h3 id="run-details-title">{t('run.details')}</h3><span className="mono">{run.run_id}</span></div><button className="icon-button" aria-label={t('run.closeDetails')} onClick={onClose}><X size={18}/></button></header>
    <dl className="run-envelope">
      <div><dt>{t('run.attempt')}</dt><dd>{runAttempt(run)}</dd></div><div><dt>{t('run.origin')}</dt><dd>{runOrigin(run)}{run.simulated?` · ${t('run.simulated')}`:''}</dd></div>
      <div><dt>{t('run.requested')}</dt><dd>{formatReceived(run.requested_at,language)}</dd></div><div><dt>{t('run.started')}</dt><dd>{run.started_at?formatReceived(run.started_at,language):'—'}</dd></div>
      <div><dt>{t('run.completedAt')}</dt><dd>{run.completed_at?formatReceived(run.completed_at,language):'—'}</dd></div><div><dt>{t('run.configuration')}</dt><dd>{configurationVersion(run)}</dd></div>
      <div><dt>{t('run.channels')}</dt><dd>{requestedChannels(run).join(', ')}</dd></div><div><dt>{t('run.coverage')}</dt><dd>{run.coverage?<>{t('run.coverageSummary',{examined:run.coverage.examined,planned:run.coverage.planned})}{run.coverage.percent!=null?` · ${t('run.coveragePercent',{percent:run.coverage.percent.toFixed(1)})}`:''}</>:t('run.notReported')}</dd></div>
      <div><dt>{t('run.samplingStrategy')}</dt><dd>{run.coverage?.strategy||t('run.notReported')}</dd></div><div><dt>{t('run.artifacts')}</dt><dd>{run.artifacts.length}</dd></div>
      <div><dt>{t('run.statusReason')}</dt><dd>{run.status_reason||'—'}</dd></div><div><dt>{t('run.backendStatus')}</dt><dd>{run.backend_status||'—'}</dd></div>
    </dl>
    {samples.length>0&&<><h4>{t('run.sampledTimestamps')}</h4><ul className="run-errors">{samples.map(sample=><li key={sample.index}><strong>{sample.timestamp_ms==null?t('run.timestampUnavailable'):`${(sample.timestamp_ms/1000).toFixed(3)} s`}</strong> — {sample.status}{sample.reason?` · ${sample.reason}`:''}</li>)}</ul>{run.coverage&&run.coverage.unexamined>0&&<p className="run-error">{t('run.partialCoverage',{count:run.coverage.unexamined})}</p>}</>}
    <h4>{t('run.errors')}</h4>{run.errors.length?<ul className="run-errors">{run.errors.map((error,index)=><li key={`${error.code}-${index}`}><strong>{error.code}</strong> — {error.message} · {t('run.retryable')}: {String(error.retryable)}</li>)}</ul>:<p className="muted">{t('run.noErrors')}</p>}
    <button className="button secondary" onClick={download}><Download size={15}/>{t('run.exportJson')}</button>
  </section></div>;
}
