import {useEffect,useRef,useState} from 'react';
import {ArrowUpRight,BookOpen,Loader2,Sparkles} from 'lucide-react';
import {apiBaseUrl} from '../data/caseSource';
import {briefingSourceRoute,explainCase,type CaseBriefing,type BriefingSource} from '../data/caseBriefing';
import {navigate} from '../app/routing';
import './caseBriefing.css';

type Props={caseId:string;recordsVersion:string;enabled:boolean};

export function CaseBriefingPanel({caseId,recordsVersion,enabled}:Props){
 const [briefing,setBriefing]=useState<CaseBriefing|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const controller=useRef<AbortController|null>(null);
 const [version,setVersion]=useState('');
 useEffect(()=>()=>controller.current?.abort(),[]);
 const stale=Boolean(briefing&&version!==recordsVersion);
 async function explain(){
  if(busy)return;
  const request=new AbortController();controller.current=request;
  const timeout=window.setTimeout(()=>request.abort(),55_000);
  setBusy(true);setError('');setBriefing(null);
  try{
   const result=await explainCase(apiBaseUrl,caseId,request.signal);
   if(!request.signal.aborted){setBriefing(result);setVersion(recordsVersion)}
  }catch(cause){
   if(request.signal.aborted)setError('The explanation was cancelled or timed out. You can still review the saved findings.');
   else setError(cause instanceof Error?cause.message:'The case explanation could not be generated.');
  }finally{window.clearTimeout(timeout);if(controller.current===request)setBusy(false)}
 }
 function citation(source:BriefingSource){
  const label=source.kind==='relationship'?'View the comparison':source.media_types.includes('audio')?'Open the voice scan':source.kind==='run'?'Review the run':'Open the evidence';
  return <a key={source.source_id} href={'#'+briefingSourceRoute(caseId,source)} onClick={event=>{event.preventDefault();navigate(briefingSourceRoute(caseId,source))}} title={source.evidence_ids.join(' ↔ ')}>{label}<span>{source.evidence_ids.join(' ↔ ')}</span><ArrowUpRight size={13}/></a>;
 }
 function links(ids:string[]){return <div className="case-briefing-links">{[...new Set(ids)].map(id=>briefing?.sources.find(source=>source.source_id===id)).filter((source):source is BriefingSource=>Boolean(source)).map(citation)}</div>}
 return <section className="case-briefing panel" aria-labelledby="case-briefing-title" aria-busy={busy}>
  <header><div><span className="eyebrow"><Sparkles size={14}/> CASE BRIEFING</span><h2 id="case-briefing-title">Explain this case</h2></div>
   <button type="button" className="button primary" disabled={!enabled||busy} onClick={()=>void explain()}>{busy?<Loader2 size={16} className="spin"/>:<BookOpen size={16}/>} {busy?'Preparing briefing…':briefing?'Explain this case again':'Explain this case'}</button>
  </header>
  <p className="case-briefing-disclosure">Shares findings, methods, limitations and evidence IDs with Prune and its AI provider. Media, filenames and extracted metadata stay local. Review the AI draft.</p>
  {!enabled&&<p className="case-briefing-muted">Connect the case backend to generate a briefing from saved examination records.</p>}
  <div role="status" aria-live="polite">{busy&&<p>Preparing briefing…</p>}{stale&&<p className="case-briefing-warning">Findings changed. Regenerate the briefing.</p>}</div>
  {error&&<p role="alert" className="case-briefing-warning">{error}</p>}
  {briefing&&!stale&&<>
   <div className="case-briefing-sections">{([
    ['Key findings',briefing.key_findings],
    ['Open questions',briefing.open_questions],
    ['Suggested next steps',briefing.next_steps],
   ] as const).map(([heading,items],index)=><section key={heading}>
    <span className="case-briefing-number">0{index+1}</span><h3>{heading}</h3>
    {heading==='Open questions'&&briefing.cautions.length>0&&<details className="case-briefing-cautions" open><summary>Recorded cautions ({briefing.cautions.length})</summary>{briefing.cautions.map((notice,i)=><div key={i}><p>{notice.text}</p>{links(notice.source_ids)}</div>)}</details>}
    <ul>{items.map((item,i)=><li key={i}><p>{item.text}</p><details><summary>Supporting record</summary><p>{item.basis}</p></details>{links(item.source_ids)}</li>)}</ul>
   </section>)}</div>
   <details className="case-briefing-records"><summary>Inspect the cited records and their limitations</summary>{briefing.sources.filter(source=>[...briefing.key_findings,...briefing.open_questions,...briefing.next_steps,...briefing.cautions].some(item=>item.source_ids.includes(source.source_id))).map(source=><article key={source.source_id}><strong>{source.source_id} · {source.evidence_ids.join(' ↔ ')}</strong><p>{source.observation}</p><p>{source.method||source.kind} · {source.execution_status} · {source.result||'No conclusion recorded'}</p><ul>{source.limitations.map((limit,i)=><li key={i}>{limit}</li>)}</ul>{citation(source)}</article>)}</details>
   <footer>Based on saved records · {new Date(briefing.generated_at).toLocaleString()} · {briefing.cached?'Reused unchanged case briefing':'Generated via Prune'} · {briefing.model}<br/>This briefing does not establish authenticity, identity or editing order.</footer>
  </>}
 </section>;
}
