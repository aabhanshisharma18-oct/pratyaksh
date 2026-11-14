import {translate} from '../i18n';
import React from 'react';
import {ProcessingSummaryData} from '../selectors/processing';
import {useI18n} from '../i18n';

export function ProcessingSummary({summary,compact=false}:{summary:ProcessingSummaryData;compact?:boolean}){
  const {t}=useI18n();
  return <section className={`processing-summary ${compact?'compact':''}`} aria-label={t('Processing status')}>
    <div className="processing-title"><div><strong>{t('Processing status')}</strong>{summary.fixture&&<span className="tiny-fixture">FIXTURE</span>}</div><span>{t('Last run')}: <b className="mono">{summary.lastRunId||t('No run recorded')}</b></span></div>
    <div className="processing-runs" aria-label={translate("Run status counts")}>{Object.entries(summary.runs).map(([status,count])=><span key={status}><strong>{count}</strong> {t(status[0].toUpperCase()+status.slice(1))}</span>)}</div>
    <div className="processing-channels">{summary.channels.map(({channel,label,counts})=><article key={channel}><strong>{label}</strong><dl>
      <div><dt>{t('Completed')}</dt><dd>{counts.completed}</dd></div><div><dt>{t('Running')}</dt><dd>{counts.running}</dd></div><div><dt>{t('Queued')}</dt><dd>{counts.queued}</dd></div><div><dt>{t('Failed')}</dt><dd>{counts.failed}</dd></div><div><dt>{t('Unsupported')}</dt><dd>{counts.unsupported}</dd></div><div><dt>{t('Not examined')}</dt><dd>{counts.not_examined+counts.not_applicable+counts.cancelled}</dd></div>
    </dl></article>)}</div>
  </section>;
}
