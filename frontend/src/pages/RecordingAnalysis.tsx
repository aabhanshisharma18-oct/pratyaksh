import {useEffect, useRef, useState} from 'react';
import {Activity} from 'lucide-react';
import {z} from 'zod';

const modules = [
  {id:'eyes', label:'Eye Movement', description:'Review eye closure scores and directional cues in sampled video frames.'},
  {id:'posture', label:'Posture', description:'Review shoulder angle, torso angle, and wrist position in sampled video frames.'},
  {id:'speech', label:'Speech', description:'See loudness and quiet intervals in an audio recording or video sound track.'},
] as const;
const resultSchema = z.object({
  method:z.string(), columns:z.array(z.string()), notes:z.string(), duration_ms:z.number(), scored:z.number(),
  rows:z.array(z.object({time_ms:z.number(),values:z.array(z.union([z.string(),z.number(),z.null()])).nullable()})),
});
type Result = z.infer<typeof resultSchema>;

export function RecordingAnalysis({baseUrl,file,kind,seek}:{baseUrl:string;file:File|null;kind:'video'|'audio';seek:(seconds:number)=>void}) {
  const [mode,setMode] = useState<typeof modules[number]['id']>(kind==='audio'?'speech':'eyes');
  const [result,setResult] = useState<Result|null>(null);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const pending = useRef<AbortController|null>(null);
  const active = modules.find(item=>item.id===mode)!;
  useEffect(()=>()=>pending.current?.abort(),[]);

  async function scan() {
    if (!file || !baseUrl || pending.current) return;
    setResult(null);
    setError('');
    if (!file.size || file.size>50*1024*1024) {
      setError('Choose a non-empty recording up to 50 MiB.');
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    const form=new FormData();
    form.set('file',file);
    const useProxy=import.meta.env.DEV && baseUrl===import.meta.env.VITE_D1_API_BASE_URL?.trim();
    try {
      const response=await fetch((useProxy?'':baseUrl.replace(/\/$/,''))+
        '/api/d1/recording-analysis/'+mode,{method:'POST',body:form,signal:controller.signal});
      const body=await response.json().catch(()=>null);
      if (!response.ok) throw new Error(typeof body?.detail==='string'?body.detail:'The recording analysis service returned HTTP '+response.status+'.');
      const parsed=resultSchema.safeParse(body);
      if (!parsed.success) throw new Error('The recording analysis service returned an unexpected result.');
      if (!controller.signal.aborted) setResult(parsed.data);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error && err.message!=='Failed to fetch'?err.message:'Could not connect to the recording analysis backend.');
    } finally {
      pending.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <section className="recording-cues" aria-label={kind==='audio'?'Audio Activity':'Recording Cues'} aria-busy={busy}>
      {kind==='video'&&<div className="detection-reference-toolbar" role="group" aria-label="Analysis module">
        {modules.map(item=><button className={'button '+(mode===item.id?'primary':'secondary')} type="button" key={item.id} disabled={busy}
          aria-pressed={mode===item.id} onClick={()=>{setMode(item.id);setResult(null);setError('');}}>{item.label==='Speech'?'Audio Activity':item.label}</button>)}
      </div>}
      <div className="detection-parameter-body">
        <p>{active.description} The scan covers up to the first 20 seconds.</p>
        {!file&&<p>Open a recording above to begin.</p>}
        {!baseUrl&&<p className="notice">Connect the detection backend to run a scan.</p>}
        <button className="button primary" type="button" disabled={!file||!baseUrl||busy} onClick={scan}><Activity size={16}/>{busy?'Analyzing…':'Run '+(mode==='speech'?'audio activity':active.label.toLowerCase())+' analysis'}</button>
      </div>
      {error&&<p className="notice" role="alert">{error}</p>}
      {result&&<section className="detection-table-scroll" aria-label="Recording findings">
        <h2 className="detection-pane-title">{mode==='speech'?'Audio Activity':active.label} Findings</h2>
        <div className="detection-parameter-body">
          <p role="status"><strong>{result.scored} of {result.rows.length} samples measured</strong> · {(result.duration_ms/1000).toFixed(1)} s · {result.method}</p>
          <p>{result.notes}</p>
          {result.scored===0&&<p>No usable single subject was visible in the sampled frames.</p>}
          <table className="detection-scan-table"><thead><tr><th scope="col">Timestamp</th>{result.columns.map(column=><th scope="col" key={column}>{column}</th>)}</tr></thead>
            <tbody>{result.rows.map(row=><tr key={row.time_ms}>
              <td><button className="button secondary" type="button" onClick={()=>seek(row.time_ms/1000)}>{(row.time_ms/1000).toFixed(2)} s</button></td>
              {row.values?row.values.map((value,index)=><td key={index}>{value??'Unavailable'}</td>):<td colSpan={result.columns.length}>No usable measurement</td>}
            </tr>)}</tbody>
          </table>
        </div>
      </section>}
  </section>;
}
