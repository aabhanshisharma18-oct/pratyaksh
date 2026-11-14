import {translate} from '../i18n';
import React,{useEffect,useMemo,useRef,useState} from 'react';
import {reportApi,type SavedReport,type ReportRevision,type RunOption} from './api';
import {classification} from '../model';
import {reportSections,defaultSections,savedSections,sectionHeading,type ReportSection} from './sections';
import {FindingTechnicalDetails} from './FindingTechnicalDetails';
import {ReportVisualDashboard,ReportVisualSummary,ReportTimeline} from './ReportVisuals';
import './reports.css';

export function ReportsWorkspace({caseId,baseUrl}:{caseId:string;baseUrl:string}){
 const api=useMemo(()=>reportApi(baseUrl),[baseUrl]);
 const [visualView,setVisualView]=useState<'dashboard'|'report'>('dashboard');
 const [settingsOpen,setSettingsOpen]=useState(true);
 const [includeArtifacts,setIncludeArtifacts]=useState(false);
 const [questions,setQuestions]=useState('');
 const [nextSteps,setNextSteps]=useState('');
 const [reviewer,setReviewer]=useState('');
 const [reviewStatus,setReviewStatus]=useState<'reviewed'|'questioned'>('reviewed');
 const [reviewNote,setReviewNote]=useState('');
 const [sections,setSections]=useState<ReportSection[]>(defaultSections);
 const [runOptions,setRunOptions]=useState<RunOption[]>([]);
 const [selectedRuns,setSelectedRuns]=useState<string[]>([]);
 const [selectRuns,setSelectRuns]=useState(false);
 const [preparer,setPreparer]=useState('');
 const [revisions,setRevisions]=useState<ReportRevision[]>([]);
 const [saved,setSaved]=useState<SavedReport|null>(null);
 const [busy,setBusy]=useState(false);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState('');
 const [message,setMessage]=useState('');
 const generation=useRef(0);
 useEffect(()=>{
  const controller=new AbortController();generation.current++;setSaved(null);setRevisions([]);setError('');setMessage('');setBusy(false);setLoading(true);setRunOptions([]);setSelectedRuns([]);setSelectRuns(false);setSections(defaultSections);setReviewer('');setReviewNote('');setReviewStatus('reviewed');setQuestions('');setNextSteps('');setIncludeArtifacts(false);setSettingsOpen(true);setVisualView('dashboard');
  Promise.all([api.list(caseId,controller.signal),api.runOptions(caseId,controller.signal)]).then(([items,options])=>{if(!controller.signal.aborted){setRevisions(items);setRunOptions(options)}})
   .catch(error=>{if(!controller.signal.aborted)setError(error instanceof Error?error.message:'Reports unavailable')})
   .finally(()=>{if(!controller.signal.aborted)setLoading(false)});
  return()=>{generation.current++;controller.abort()};
 },[api,caseId]);
 async function perform(action:()=>Promise<void>){
  const current=generation.current;setBusy(true);setError('');setMessage('');
  try{await action()}catch(error){if(current===generation.current)setError(error instanceof Error?error.message:'Report request failed')}
  finally{if(current===generation.current)setBusy(false)}
 }
 async function save(){
  const current=generation.current;
  await perform(async()=>{
   const result=await api.save(caseId,preparer.trim(),selectRuns?selectedRuns:undefined,sections,{questions:questions.trim(),next_steps:nextSteps.trim(),include_artifacts:includeArtifacts});
   if(current!==generation.current)return;
   setSaved(result);setSettingsOpen(false);setRevisions(items=>[{report_id:result.snapshot.report_id,revision:result.snapshot.revision,sha256:result.sha256},...items]);
   setMessage(`Revision ${result.snapshot.revision} saved on the server.`);
  });
 }
 async function reopen(id:string){const current=generation.current;setSaved(null);await perform(async()=>{const result=await api.get(id);if(current===generation.current){setSaved(result);setSettingsOpen(false)}})}
 async function saveReview(){
  if(!saved)return;
  const source=saved.snapshot.report_id,current=generation.current;
  await perform(async()=>{
   const result=await api.review(source,reviewer.trim(),reviewStatus,reviewNote.trim());
   if(current!==generation.current)return;
   setSaved(result);setRevisions(items=>[{report_id:result.snapshot.report_id,revision:result.snapshot.revision,sha256:result.sha256},...items]);
   setReviewNote('');setMessage(`Review saved as revision ${result.snapshot.revision}. Source report remains unchanged.`);
  });
 }
 const report=saved?.snapshot;
 const visibleSections=savedSections(report?.sections);
 const heading=(id:ReportSection)=>sectionHeading(id,visibleSections);
 return <div className={'reports-layout d5-workspace'+(report&&!settingsOpen?' settings-collapsed':'')}>
  <section className="panel report-settings">
   <h2>{translate("Save a report")}</h2><p className="muted">{translate("Enter your name and save a report version containing this case’s recorded findings and notes. Saving a report does not run new analysis or decide whether a file is genuine.")}</p>
   <label className="field">{translate("Prepared by")}<input maxLength={200} value={preparer} onChange={event=>setPreparer(event.target.value)} placeholder={translate("Your name")}/></label>
   <label className="field">{translate("Questions examined (analyst supplied)")}<textarea maxLength={2000} value={questions} onChange={event=>setQuestions(event.target.value)} placeholder={translate("State the questions this examination addresses")}/></label>
   <label className="field">{translate("Recommended next steps (analyst supplied)")}<textarea maxLength={2000} value={nextSteps} onChange={event=>setNextSteps(event.target.value)} placeholder={translate("Record follow-up steps without asserting unsupported conclusions")}/></label>
   <label className="field">{translate("Run selection")}<select disabled={busy||loading} value={selectRuns?'selected':'all'} onChange={event=>setSelectRuns(event.target.value==='selected')}><option value="all">{translate("All registered findings")}</option><option value="selected">{translate("Select finished runs")}</option></select></label>
   {selectRuns&&<fieldset disabled={busy||loading}><legend>{translate("Finished runs to include")}</legend>{runOptions.length?runOptions.map(run=><label key={run.run_id} style={{display:'block',marginBottom:10}}><input type="checkbox" disabled={!run.selectable} checked={selectedRuns.includes(run.run_id)} onChange={event=>setSelectedRuns(current=>event.target.checked?[...current,run.run_id]:current.filter(id=>id!==run.run_id))}/>{run.run_id} · {run.status} · {run.finding_count} {translate("findings")}<small style={{display:'block'}}>{run.evidence_ids.join(', ')} · {run.status_source==='run_record'?'Saved run status':'Status derived from registered findings'}</small></label>):<p>{translate("No registered runs with findings.")}</p>}<p>{translate("Running/queued runs cannot be selected. Failed and partial runs remain available so missing checks stay visible.")}</p></fieldset>}
   <fieldset disabled={busy||loading}><legend>{translate("Included report sections")}</legend>{reportSections.map(section=><label key={section.id} style={{display:'block',marginBottom:8}}><input type="checkbox" disabled={section.required} checked={sections.includes(section.id)} onChange={event=>setSections(current=>event.target.checked?[...current,section.id]:current.filter(id=>id!==section.id))}/>{section.label}{section.required?' (required)':''}</label>)}<p>{translate("Selection controls the readable report. JSON/ZIP retain the complete saved technical record; this is not a redaction tool.")}</p></fieldset>
   <label><input type="checkbox" disabled={busy||loading} checked={includeArtifacts} onChange={event=>setIncludeArtifacts(event.target.checked)}/>{translate('Include verified supporting files in ZIP')}</label>
   <p>{translate('Only D2 derivatives linked to this case, evidence hash and source run can be included. Missing or mismatched files are excluded. Originals are never included.')}</p>
   <p className="notice">{translate("Preparer names are self-declared. Each save includes findings and reviewer notes within the chosen run scope.")}</p>
   {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
   <button className="button primary full" disabled={busy||loading||!preparer.trim()||(selectRuns&&!selectedRuns.length)} onClick={save}>{busy?translate("Working…"):translate("Save report revision")}</button>
   <button className="button secondary full" disabled={busy||!report} onClick={()=>report&&perform(()=>api.download(report.report_id,'json'))}>{translate("Export saved JSON")}</button>
   <button className="button secondary full" disabled={busy||!report} onClick={()=>report&&perform(()=>api.download(report.report_id,'zip'))}>{translate("Export ZIP with manifest")}</button>
   <button className="button secondary full" disabled={busy||!report} onClick={()=>window.print()}>{translate("Print / Save as PDF")}</button>
   <fieldset disabled={busy||!report}><legend>{translate("Review selected saved revision")}{report?` ${report.revision}`:''}</legend>
    <label className="field">{translate("Reviewer name")}<input maxLength={200} value={reviewer} onChange={event=>setReviewer(event.target.value)}/></label>
    <label className="field">{translate("Review status")}<select value={reviewStatus} onChange={event=>setReviewStatus(event.target.value as 'reviewed'|'questioned')}><option value="reviewed">{translate("Reviewed")}</option><option value="questioned">{translate("Questioned / needs follow-up")}</option></select></label>
    <label className="field">{translate("Review note")}<textarea maxLength={2000} value={reviewNote} onChange={event=>setReviewNote(event.target.value)} placeholder={translate("Record your interpretation or concerns")}/></label>
    <p>{translate("Reviewer identity is self-declared. This records review of the selected snapshot; it does not certify authenticity or legal admissibility. Draft run/section choices do not affect this review.")}</p>
    <button className="button primary full" disabled={busy||!report||!reviewer.trim()||!reviewNote.trim()} onClick={saveReview}>{translate("Save review as new revision")}</button>
   </fieldset>
   <div className="revision-history"><h3>{translate("Saved revisions")}</h3>{loading?<p role="status">{translate("Loading revisions…")}</p>:!revisions.length?<p>{translate("No saved revisions yet.")}</p>:revisions.map(item=><button key={item.report_id} className="button subtle full" disabled={busy} aria-pressed={report?.report_id===item.report_id} onClick={()=>reopen(item.report_id)}>{translate("Revision")} {item.revision}{report?.report_id===item.report_id?translate(" · selected"):''}</button>)}</div>
  </section>
  <div className="d5-report-content"><div className="d5-view-toolbar"><div className="d5-view-buttons" role="group" aria-label={translate('Report presentation')}><button type="button" disabled={!report} aria-pressed={visualView==='dashboard'} onClick={()=>setVisualView('dashboard')}>{translate('Analysis dashboard')}</button><button type="button" disabled={!report} aria-pressed={visualView==='report'} onClick={()=>setVisualView('report')}>{translate('Visual report')}</button></div>{report&&<button type="button" className="button secondary" aria-expanded={settingsOpen} onClick={()=>setSettingsOpen(value=>!value)}>{translate(settingsOpen?'Hide configuration':'Report configuration')}</button>}</div>
  {report&&<div className="d5-dashboard-panel" hidden={visualView!=='dashboard'}><ReportVisualDashboard key={report.report_id} report={report}/></div>}
  <section className="report-preview d5-document-view" hidden={!!report&&visualView!=='report'}><div className="preview-title">{translate("SAVED DOCUMENT PREVIEW")}</div>{!report?<div className="panel"><h2>{translate("Select a saved revision")}</h2><p>{translate("Save a report or open a revision. Downloads and printing use that exact saved record.")}</p></div>:<article className="paper">
   <div className="paper-brand">{translate("PRATYAKSH · FORENSIC REVIEW")}</div><div className="paper-rule"/>
   <p className="paper-eyebrow">{translate("INVESTIGATION REPORT · REVISION")} {report.revision}</p><h2>{report.case.title}</h2>
   <p>{report.report_id}<br/>{report.case.id} · {report.generated_at}<br/>{translate("Prepared by")} {report.preparer} {translate("(self-declared)")}</p>
   <div className="paper-warning">{report.fixture?translate("Includes illustrative findings"):translate("Registered case records")} · {report.review_status==='unreviewed'?'Unreviewed report':report.review_status==='reviewed'?'Reviewed (self-declared)':'Questioned / needs follow-up'}</div>
   <ReportVisualSummary report={report} compact/><ReportTimeline report={report}/>
   {report.review_history?.length? <section><h3>{translate("Report review history")}</h3>{report.review_history.map((review,index)=><div key={index}><p><b>{review.reviewer}</b> {translate("(self-declared) ·")} {review.status} · {review.reviewed_at}</p><p style={{whiteSpace:'pre-wrap'}}>{review.note}</p><p>{translate("Reviewed source:")} {review.source_report_id}<br/>{translate("Source SHA-256:")} {review.source_report_sha256}</p></div>)}</section>:null}
   {report.parent_report_id&&<p>{translate("Based on saved report")} {report.parent_report_id}{translate(". Original preparation:")} {report.prepared_at}</p>}
   <h3>{heading('methods')}</h3><p>{report.case.description||translate("No case description recorded.")}</p><p style={{whiteSpace:'pre-wrap'}}>{translate("Questions examined (analyst supplied):")} {report.analyst_context?.questions||'Not recorded'}</p>
   <p>{report.evidence.length} {translate("evidence records ·")} {report.findings.length} {translate("registered findings. No new inference was performed when this revision was saved.")}</p>
   {report.run_selection&&<p>{translate("Run scope:")} {report.run_selection.mode==='selected'?'Selected finished runs':'All registered findings'}<br/>{translate("Run IDs:")} {report.run_selection.run_ids.join(', ')||'None'}<br/>{report.run_selection.excluded_finding_count} {translate("registered findings excluded by run selection.")}</p>}
   {visibleSections.includes('evidence')&&<><h3>{heading('evidence')}</h3>{report.evidence.length?report.evidence.map(item=><section key={item.evidence_id}><h4>{item.evidence_id} · {item.filename}</h4><p>{item.media_type} · {item.role} · {item.size_bytes} {translate("bytes")}<br/>SHA-256: {item.sha256}<br/>{translate("Hash source:")} {item.hash_source} · {item.preserved?translate("Original preserved"):translate("Inventory only")}<br/>{translate("Registered")} {item.registered_at} {translate("by")} {item.registered_by} {translate("(self-declared)")}<br/>{translate("Supplied by (reported):")} {item.receipt?.supplied_by||'Not recorded'}<br/>{translate("Collection reference (reported):")} {item.receipt?.collection_reference||'Not recorded'}<br/>{translate("Receipt note:")} {item.receipt?.note||'Not recorded'}</p></section>):<p>{translate("No registered evidence.")}</p>}
   </>}<h3>{heading('findings')}</h3>{report.findings.length?[...report.findings].sort((a,b)=>a.finding.evidence_id.localeCompare(b.finding.evidence_id)||a.finding.category.localeCompare(b.finding.category)||a.finding_id.localeCompare(b.finding_id)).map(record=><section key={record.finding_id}><h4>{record.finding.evidence_id} · {record.finding.category} · {record.finding_id}</h4><p>{classification(record.finding)} {translate("· Execution:")} {record.finding.execution_status}</p><p>{record.finding.observation}</p><p>{translate("Evidence:")} {record.finding.evidence_id} {translate("· Run:")} {record.finding.run_id}<br/>{translate("Method:")} {record.finding.method} · {record.finding.method_version}<br/>{translate("Scope:")} {record.finding.scope}<br/>{translate("Source SHA-256:")} {record.finding_sha256}</p>
    {record.finding.error&&<p>{translate("Error:")} {record.finding.error.code} · {record.finding.error.message}</p>}
    {record.finding.score&&<p>{translate("Score:")} {record.finding.score.value??translate("Unavailable")} {translate("· Range:")} {record.finding.score.range.join(' to ')} {translate("· Positive class:")} {record.finding.score.positive_class}<br/>{record.finding.score.interpretation} {translate("· Calibration:")} {record.finding.score.calibration_status}</p>}
    <p>{translate("Artifact references:")} {record.finding.support_refs.join(', ')||translate("None recorded")}</p>{record.finding.limitations.map((text,index)=><p key={index}>{translate("Limitation:")} {text}</p>)}
    <FindingTechnicalDetails finding={record.finding}/>
   </section>):<p>{translate("No registered findings. This report makes no authenticity determination.")}</p>}
   <h3>{heading('coverage')}</h3><table><thead><tr><th>{translate("Evidence")}</th><th>{translate("Channel")}</th><th>{translate("Recorded checks")}</th></tr></thead><tbody>{report.coverage.map(item=><tr key={item.evidence_id+item.category}><td>{item.evidence_id}</td><td>{item.category}</td><td>{item.status==='not_assessed'?'Not assessed in report scope':item.finding_ids.join(', ')}</td></tr>)}</tbody></table><p>{translate("A recorded check can be failed or inconclusive. See each finding’s execution status.")}</p>
   {visibleSections.includes('notes')&&<><h3>{heading('notes')}</h3>{Object.values(report.review_notes).flat().length?Object.values(report.review_notes).flat().map(note=><p key={note.note_id}>{note.text}<br/>{note.author} {translate("(self-declared) ·")} {note.status} · {note.created_at}</p>):<p>{translate("No reviewer notes recorded.")}</p>}
   </>}<h3>{heading('limitations')}</h3>{report.limitations.map((text,index)=><p key={index}>{text}</p>)}
   <section><h3>{translate("Saved run context and supporting references")}</h3>{report.source_references?<>
    {report.source_references.runs.map(run=><div key={run.run_id}><h4>{run.run_id} · {run.status.replaceAll('_',' ')}</h4>{run.record?<dl>{Object.entries(run.record).map(([key,value])=><React.Fragment key={key}><dt>{key}</dt><dd><code>{value===null?'Not recorded':JSON.stringify(value)}</code></dd></React.Fragment>)}</dl>:<p>{translate("No matching saved run context captured. Settings are not inferred.")}</p>}</div>)}
    {report.source_references.artifacts.length?report.source_references.artifacts.map((artifact,index)=><p key={index}><b>{artifact.reference}</b> · {artifact.status.replaceAll('_',' ')}<br/>{translate("Finding:")} {artifact.finding_id} {translate("· Evidence:")} {artifact.evidence_id} {translate("· Run:")} {artifact.run_id}<br/>{translate("Recorded metadata:")} {artifact.metadata?JSON.stringify(artifact.metadata):'Not available'}<br/>{artifact.bytes_verified&&artifact.bytes_included?translate("Artifact bytes verified and frozen for ZIP export."):translate("Artifact bytes: not verified, not included.")}{artifact.verification&&<> {translate("Verification:")} {artifact.verification}</>}</p>):<p>{translate("No supporting artifact references in the selected findings.")}</p>}
    {report.source_references.limitations.map((text,index)=><p key={index}>{text}</p>)}
   </>:<p>{translate("No run-context snapshot was captured in this historical revision.")}</p>}</section>
   {report.package_policy&&<p>{translate('Package policy:')} {report.package_policy.verified_artifact_count} {translate('verified supporting files; original media excluded.')}</p>}
   <section><h3>{translate("Investigator follow-up")}</h3><p style={{whiteSpace:'pre-wrap'}}>{report.analyst_context?.next_steps||'No recommended next steps recorded.'}</p>{report.analyst_context&&<p>{translate("Entered by")} {report.analyst_context.author} {translate("(self-declared). These are analyst statements, separate from automated findings.")}</p>}</section>
   <section><h3>{translate("Saved case audit summary")}</h3>{report.audit_summary?<>
    <p>{translate("Captured")} {report.audit_summary.captured_at} {translate("· Case-wide scope ·")} {report.audit_summary.included_count} {translate("included events")}{report.audit_summary.truncated?' · Earlier events omitted (limit reached)':''}</p>
    <ul>{Object.entries(report.audit_summary.counts_by_type).map(([type,count])=><li key={type}>{type}: {count}</li>)}</ul>
    {report.audit_summary.events.map(event=><p className="audit-event" key={event.id}><b>{event.type}</b> · {event.created_at}<br/>{event.summary}<br/>{translate("Actor:")} {event.actor} {translate("(self-declared) · Event:")} {event.id}<br/>{translate("Evidence:")} {event.evidence_id||'Not applicable'} {translate("· Run:")} {event.run_id||'Not applicable'}</p>)}
    {report.audit_summary.limitations.map((text,index)=><p key={index}>{text}</p>)}
   </>:<p>{translate("No audit snapshot was captured in this historical revision.")}</p>}</section>
   <p>{translate("Readable sections:")} {reportSections.filter(section=>visibleSections.includes(section.id)).map(section=>section.label).join(', ')}{translate(". The machine-readable export retains the full saved technical record.")}</p>
   <footer>{translate("Report SHA-256 (canonical JSON):")} {saved?.sha256}</footer>
  </article>}</section></div>
 </div>;
}
