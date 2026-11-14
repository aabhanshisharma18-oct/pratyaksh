import {useEffect,useRef,useState} from 'react';

type Stage={status:string;error?:string;reason?:string};
type Job={
 id:string;case_id:string;status:string;message:string;updated_at?:string;
 files:Array<{name:string;media_type:string|null;status:string;reason?:string;evidence_id?:string;detection?:Stage;authentication?:Stage}>;
 provenance:Stage;report:Stage;
};

export function CaseAutomationProgress({baseUrl,caseId,onUpdated}:{baseUrl:string;caseId:string;onUpdated:()=>void}){
 const[job,setJob]=useState<Job|null>(null),[error,setError]=useState('');
 const callback=useRef(onUpdated);
 callback.current=onUpdated;
 const changed=useRef('');
 useEffect(()=>{
  const controller=new AbortController();
  let timer:ReturnType<typeof setTimeout>;
  changed.current='';setJob(null);setError('');
  async function poll(){
   try{
    const response=await fetch(baseUrl.replace(/\/$/,'')+'/api/cases/'+encodeURIComponent(caseId)+'/automation',{signal:controller.signal});
    if(!response.ok)throw new Error('Could not load automatic case progress.');
    const body=await response.json() as {job:Job|null};
    if(controller.signal.aborted)return;
    setJob(body.job);setError('');
    if(body.job){
     const version=body.job.updated_at??body.job.status;
     if(version!==changed.current){changed.current=version;callback.current();}
     if(['queued','running'].includes(body.job.status))timer=setTimeout(poll,2000);
    }
   }catch(err){
    if(!controller.signal.aborted){setError(err instanceof Error?err.message:'Progress unavailable.');timer=setTimeout(poll,5000);}
   }
  }
  void poll();
  return()=>{controller.abort();clearTimeout(timer);};
 },[baseUrl,caseId]);
 async function resume(){
  if(!job)return;
  const response=await fetch(baseUrl.replace(/\/$/,'')+'/api/automation/'+encodeURIComponent(job.id)+'/resume',{method:'POST'});
  if(!response.ok){setError('Could not resume this analysis. Refresh and retry.');return;}
  // Remount the monitor so polling resumes after a terminal job.
  callback.current();window.location.reload();
 }
 if(!job&&!error)return null;
 return <section className="panel automation-progress" aria-label="Automatic case analysis">
  <div className="panel-heading"><h2>Automatic case analysis</h2><span className="badge neutral">{job?.status??'Status unavailable'}</span></div>
  {error&&<p role="alert">{error}</p>}
  {job&&<div className="panel-body">
   <p role="status">{job.message}</p>
   <p>Files are routed by decoded media type. Each applicable check records its own result and limitations.</p>
   <div className="detection-table-scroll"><table><thead><tr><th>ZIP member</th><th>Media</th><th>Detection</th><th>Authentication &amp; tampering</th></tr></thead>
    <tbody>{job.files.map(item=><tr key={item.name}><td>{item.name}{item.reason&&<small style={{display:'block'}}>{item.reason}</small>}</td><td>{item.media_type??'Unsupported'}</td>
     <td>{item.detection?.status??item.status}{item.detection?.error&&<small style={{display:'block'}}>{item.detection.error}</small>}</td>
     <td>{item.authentication?.status??(item.media_type?'pending':'skipped')}{item.authentication?.error&&<small style={{display:'block'}}>{item.authentication.error}</small>}</td></tr>)}</tbody>
   </table></div>
   <p>Case relationships · {job.provenance.status}{job.provenance.error&&' · '+job.provenance.error}</p>
   <p>Saved report · {job.report.status}{job.report.error&&' · '+job.report.error}</p>
   {['interrupted','failed','partial'].includes(job.status)&&<button type="button" className="button secondary" onClick={()=>void resume().catch(()=>setError('Could not reach the backend.'))}>Resume / retry unfinished analysis</button>}
  </div>}
 </section>;
}
