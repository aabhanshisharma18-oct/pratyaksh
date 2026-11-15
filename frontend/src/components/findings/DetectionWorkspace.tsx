import {caseOriginalUrl} from '../../data/caseSource';
import {FaceScoreStability} from '../../pages/FaceScoreStability';
import {translate} from '../../i18n';
import type {DetectionScan} from '../../data/detectionScan';
import {useEffect,useState, type ReactNode} from 'react';
import {FileText, Play, ShieldCheck} from 'lucide-react';
import {type Channel, type Evidence, type Finding} from '../../model';
import './detection.css';
import {readSession,writeSession} from '../../data/stateRestoration';

const layers = [
  {id:'synthetic_media', title:'AI-generation signals', channels:['synthetic_media']},
  {id:'tampering', title:'Manipulation or editing', channels:['tampering']},
  {id:'integrity', title:'File integrity', channels:['integrity']},
  {id:'provenance', title:'Source and provenance', channels:['provenance']},
] as const;

type Props = {
  evidence: Evidence;
  findings: Finding[];
  selectedFindingId?: string | null;
  onReport: () => void;
  onRun: () => void;
  onVerify?: () => void;
  verifying: boolean;
  scanning: boolean;
  scan?: DetectionScan;
  scanError?: string;
  detectionBaseUrl?: string;
  onAttachSample?: () => void;
  renderFindings: (findings: Finding[], channels: readonly Channel[]) => ReactNode;
};

function findingsFor(layer: typeof layers[number]['id'], evidence: Evidence, findings: Finding[]) {
  void evidence;
  return findings.filter(finding=>finding.category===layer);
}

export function DetectionWorkspace({evidence, findings, selectedFindingId, onReport, onRun, onVerify, verifying, onAttachSample, renderFindings, scanning, scan, scanError, detectionBaseUrl}: Props) {
  const defaultLayer=()=>'synthetic_media' as const;
  const restored=readSession(`pratyaksh-layer:${evidence.id}`);
  const [active, setActive] = useState<typeof layers[number]['id']>(()=>layers.some(item=>item.id===restored)?restored as typeof layers[number]['id']:defaultLayer());
  useEffect(()=>{const value=readSession(`pratyaksh-layer:${evidence.id}`);setActive(layers.some(item=>item.id===value)?value as typeof layers[number]['id']:defaultLayer())},[evidence.id,evidence.type]);
  useEffect(()=>writeSession(`pratyaksh-layer:${evidence.id}`,active),[evidence.id,active]);
  const selectedFinding=findings.find(finding=>finding.finding_id===selectedFindingId);
  const selectedCategory=selectedFinding?.category;
  useEffect(()=>{
    if(!selectedCategory)return;
    setActive(selectedCategory);
  },[selectedFindingId,selectedCategory,evidence.type]);
  const layer = layers.find(item => item.id === active)!;
  const results = findingsFor(active, evidence, findings);
  return <>
    <aside className="detection-file" aria-label={translate("File and analysis details")}>
      <div className="detection-heading"><h2>{translate("Evidence details")}</h2>
        <span className="badge">{evidence.fixture?'Sample evidence':findings.length?'Findings available':'Awaiting analysis'}</span>
      </div>
      <dl className="detection-properties">
        <div><dt>{translate("Evidence ID")}</dt><dd className="mono">{evidence.id}</dd></div>
        <div><dt>{translate("File name")}</dt><dd>{evidence.name}</dd></div>
        <div><dt>{translate("Media type")}</dt><dd>{evidence.mime || evidence.type}</dd></div>
        <div><dt>{translate("Size")}</dt><dd>{evidence.size}</dd></div>
        <div><dt>{translate("Received")}</dt><dd>{evidence.received}</dd></div>
        <div><dt>SHA-256</dt><dd className="mono">{evidence.hash || 'Unavailable'}</dd></div>
      </dl>
      <div className="detection-actions">
        <button className="button primary" onClick={onRun} disabled={scanning||evidence.fixture||!evidence.source}><Play size={14}/>{scanning?'Running applicable checks…':'Run analysis'}</button>
        <button className="button secondary" onClick={onReport}><FileText size={14}/>Review & Report</button>
        {onVerify && <button className="button secondary" disabled={verifying} onClick={onVerify}><ShieldCheck size={14}/>{translate("Verify stored SHA-256")}</button>}
        {onAttachSample && <button className="button secondary" onClick={onAttachSample}>{translate("Attach sample finding")}</button>}
      </div>
      {scanError&&<p role="alert">{scanError}</p>}
      {scan&&<div className="notice" role="status"><div><strong>{scan.summary.result === 'inconclusive' ? 'Inconclusive' : 'Unavailable'} · {scan.summary.completed_checks}/{scan.summary.total_checks} {translate("checks completed")}</strong><p>{scan.summary.reason}</p></div></div>}
      {evidence.verification && <p role="status">{translate("Stored file check:")} {evidence.verification.status}</p>}
    </aside>
    <section className="detection-results" aria-label={translate("Analysis results")}>
      <div className="detection-tabs" role="tablist" aria-label={translate("Analysis views")} onKeyDown={event=>{const index=layers.findIndex(item=>item.id===active);const next=event.key==='ArrowRight'?index+1:event.key==='ArrowLeft'?index-1:event.key==='Home'?0:event.key==='End'?layers.length-1:index;if(next!==index){event.preventDefault();setActive(layers[(next+layers.length)%layers.length].id)}}}>
        {layers.map(item=><button key={item.id} role="tab" aria-selected={active===item.id} tabIndex={active===item.id?0:-1} onClick={()=>setActive(item.id)}>{item.title}</button>)}
      </div>
      {results.length ? renderFindings(results, layer.channels) : <div className="detection-summary">
        <h2>{layer.title}</h2><p>{translate("No results are available for this layer.")}</p>
      </div>}
      {active === 'synthetic_media' && evidence.type === 'image' && !evidence.fixture &&
        evidence.source && detectionBaseUrl && <FaceScoreStability baseUrl={detectionBaseUrl}
          expectedHash={/^[a-f0-9]{64}$/i.test(evidence.hash) ? evidence.hash : undefined}
          loadImage={async signal => {
            const source = evidence.preserved && evidence.caseId
              ? caseOriginalUrl(evidence.caseId, evidence.id)
              : evidence.source!;
            const response = await fetch(source, {signal});
            if (!response.ok) throw new Error('The evidence photo could not be read.');
            return response.blob();
          }}/>}
    </section>
  </>;
}
