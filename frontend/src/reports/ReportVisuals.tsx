import React,{useEffect,useMemo,useState,useRef} from 'react';
import {ReactFlow,Background,Controls,MarkerType,type Node,type Edge} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {AudioLines,FileImage,Film,GitBranch,BarChart3,Clock3,Layers} from 'lucide-react';
import {translate as t} from '../i18n';
import {channels,classification} from '../model';
import {coverageStates,reportMilestones,reportVisualModel,scoreGroups,type ReportData} from './visualModel';
import './visuals.css';

const stateLabels={completed:'Completed',partial:'Partial',failed:'Failed',unsupported:'Unsupported',running:'Running',queued:'Queued',cancelled:'Cancelled',not_applicable:'Not applicable',not_assessed:'Not assessed'};
const utc=(value:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(value));

export function ReportVisualSummary({report,compact=false}:{report:ReportData;compact?:boolean}){
 const model=reportVisualModel(report);
 return <section className={'d5-visual-summary'+(compact?' compact':'')} aria-label={t('Examination overview')}>
  <div className="d5-summary-heading"><div><span className="d5-kicker">{t('SAVED EXAMINATION OVERVIEW')}</span><h3>{t('Four channels. Separate conclusions.')}</h3></div><span className="d5-scope-label">{report.evidence.length} {t('evidence items')} · {report.findings.length} {t('findings')}</span></div>
  {report.fixture&&<p className="d5-fixture-label">{t('Includes illustrative findings')}</p>}
  <div className="d5-channel-cards">{model.channelSummaries.map(channel=><div key={channel.key} className={'d5-channel-card '+channel.key}>
   <span className="d5-channel-name">{t(channel.name)}</span><strong>{channel.count} {t('recorded observations')}</strong>
   {channel.labels.length?<ul>{channel.labels.map(([label,count])=><li key={label}><span>{t(label)}</span><b>{count}</b></li>)}</ul>:<p>{t('No recorded observations')}</p>}
   {channel.missing>0&&<small>{channel.missing} {t('evidence items not assessed in this channel')}</small>}
  </div>)}</div>
  <div className="d5-coverage-heading"><h4>{t('Examination coverage')}</h4><span>{model.total} {t('evidence-channel cells')}</span></div>
  {model.total>0?<><div className="d5-coverage-bar" role="img" aria-label={coverageStates.filter(s=>model.counts[s]).map(s=>`${t(stateLabels[s])}: ${model.counts[s]}`).join(', ')}>{coverageStates.filter(s=>model.counts[s]).map(s=><span key={s} className={'d5-state-'+s} style={{width:`${model.counts[s]/model.total*100}%`}}/>)}</div><div className="d5-coverage-key">{coverageStates.filter(s=>model.counts[s]).map(s=><span key={s}><i className={'d5-state-'+s}/>{t(stateLabels[s])}<b>{model.counts[s]}</b></span>)}</div></>:<p>{t('No evidence registered in this revision.')}</p>}
  <p className="d5-v-caption">{t('Coverage counts evidence × channel cells, not finding totals or authenticity probabilities. Partial means completed and unavailable checks coexist.')}</p>
 </section>;
}

function EvidenceMap({report,selected,onSelect}:{report:ReportData;selected:string;onSelect:(id:string)=>void}){
 const {nodes,edges,omitted}=useMemo(()=>{
  const evidence=report.evidence.slice(0,12),ids=new Set(evidence.map(e=>e.evidence_id));
  const runIds=[...new Set(report.findings.filter(r=>ids.has(r.finding.evidence_id)).map(r=>r.finding.run_id))].slice(0,20);
  const references=(report.source_references?.artifacts??[]).filter(a=>ids.has(a.evidence_id)&&runIds.includes(a.run_id));
  const artifacts=[...new Map(references.map(a=>[a.run_id+'|'+a.reference,a])).values()].slice(0,24);
  const nodes:Node[]=evidence.map((e,i)=>({id:'e:'+e.evidence_id,position:{x:0,y:i*95},data:{label:<><b>{e.evidence_id}</b><span>{e.filename}</span><small>{t(e.media_type)}</small></>},className:'d5-map-evidence',selected:e.evidence_id===selected}));
  runIds.forEach((id,i)=>nodes.push({id:'r:'+id,position:{x:260,y:i*95},data:{label:<><small>{t('Analysis run')}</small><span>{id}</span></>},className:'d5-map-run'}));
  artifacts.forEach((a,i)=>nodes.push({id:'a:'+a.run_id+'|'+a.reference,position:{x:520,y:i*95},data:{label:<><small>{t('Supporting reference')}</small><span>{a.reference}</span><small>{t(a.bytes_verified?'Verified bytes':'Reference only')}</small></>},className:'d5-map-artifact'}));
  const edges:Edge[]=[];
  for(const r of report.findings){if(ids.has(r.finding.evidence_id)&&runIds.includes(r.finding.run_id)){const id=r.finding.evidence_id+'|'+r.finding.run_id;if(!edges.some(e=>e.id===id))edges.push({id,source:'e:'+r.finding.evidence_id,target:'r:'+r.finding.run_id,type:'smoothstep',markerEnd:{type:MarkerType.ArrowClosed},label:t('Analysis')})}}
  artifacts.forEach(a=>edges.push({id:'ref:'+a.run_id+'|'+a.reference,source:'r:'+a.run_id,target:'a:'+a.run_id+'|'+a.reference,type:'smoothstep',style:{strokeDasharray:a.bytes_verified?undefined:'5 4'},markerEnd:{type:MarkerType.ArrowClosed}}));
  return {nodes,edges,omitted:evidence.length<report.evidence.length||runIds.length<new Set(report.findings.map(r=>r.finding.run_id)).size||artifacts.length<references.length};
 },[report,selected]);
 return <section className="d5-v-panel"><div className="d5-v-heading"><h3><GitBranch size={17}/>{t('Evidence relationship map')}</h3><span>{t('Recorded links only')}</span></div>
  {nodes.length?<div className="d5-evidence-map" aria-label={t('Evidence linked to saved runs and supporting artifact references')}><ReactFlow key={report.report_id} nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} zoomOnScroll={false} minZoom={0.15} maxZoom={1.5} onNodeClick={(_,node)=>{if(node.id.startsWith('e:'))onSelect(node.id.slice(2))}}><Background/><Controls showInteractive={false}/></ReactFlow></div>:<p>{t('No evidence registered in this revision.')}</p>}
  <p className="d5-v-caption">{t('This is an evidence-to-run reference map. It does not establish geographic origin, person identity or an editing history.')}{omitted&&<> {t('Map display is limited; the coverage matrix includes the full inventory.')}</>}</p>
 </section>;
}

function SavedScorePlot({report,evidenceId}:{report:ReportData;evidenceId:string}){
 const groups=scoreGroups(report,evidenceId),[chosen,setChosen]=useState(''),[pointId,setPointId]=useState('');
 const plotRef=useRef<HTMLDivElement>(null),[plotWidth,setPlotWidth]=useState(520);
 useEffect(()=>{if(!plotRef.current)return;const observer=new ResizeObserver(entries=>setPlotWidth(Math.max(160,Math.round(entries[0].contentRect.width))));observer.observe(plotRef.current);return()=>observer.disconnect()},[Boolean(groups.length)]);
 const group=groups.find(g=>g.id===chosen)??groups[0];
 useEffect(()=>{setChosen('');setPointId('')},[report.report_id,evidenceId]);
 if(!group)return <section className="d5-v-panel"><div className="d5-v-heading"><h3><BarChart3 size={17}/>{t('Saved observation scores')}</h3></div><div className="d5-chart-empty"><BarChart3 size={30}/><p>{t('No completed numeric scores for this evidence.')}</p><small>{t('Unavailable results are not plotted as zero.')}</small></div></section>;
 const timed=group.points.every(p=>p.time!==null),points=[...group.points].sort((a,b)=>timed?a.time!-b.time!:0);
 const xs=points.map((p,i)=>timed?p.time!/1000:i+1),minX=Math.min(...xs),maxX=Math.max(...xs);
 const x=(value:number)=>minX===maxX?(50+plotWidth-20)/2:50+(value-minX)/(maxX-minX)*(plotWidth-70);
 const y=(value:number)=>170-(value-group.range[0])/(group.range[1]-group.range[0])*140;
 const selected=points.find(p=>p.id===pointId)??points[0];
 return <section className="d5-v-panel"><div className="d5-v-heading"><h3><BarChart3 size={17}/>{t('Saved observation scores')}</h3><span>{t('Raw score')}</span></div>
  {groups.length>1&&<label className="field">{t('Method and run')}<select value={group.id} onChange={event=>{setChosen(event.target.value);setPointId('')}}>{groups.map(g=><option key={g.id} value={g.id}>{g.method} · {g.runId} · {g.positiveClass}</option>)}</select></label>}
  <p className="d5-v-caption">{group.method} · {group.positiveClass} · {group.calibration}</p>
  <div ref={plotRef}><svg className="d5-score-plot" viewBox={`0 0 ${plotWidth} 225`} role="img" aria-label={`${t('Saved raw scores')}: ${points.map(p=>p.value).join(', ')}`}>
   {[0,.5,1].map(ratio=><g key={ratio}><line x1="50" x2={plotWidth-20} y1={170-ratio*140} y2={170-ratio*140} className="d5-chart-grid"/><text x="8" y={175-ratio*140}>{Number((group.range[0]+ratio*(group.range[1]-group.range[0])).toPrecision(4))}</text></g>)}
   {points.map((p,i)=><circle key={p.id} cx={x(xs[i])} cy={y(p.value)} r={p.id===selected.id?7:5} className="d5-score-point"><title>{p.id}: {p.value}{timed?` @ ${xs[i]}s`:''}</title></circle>)}
   {[minX,...(maxX>minX?[maxX]:[])].map(value=><text key={value} x={x(value)} y="193" textAnchor="middle">{Number(value.toPrecision(5))}</text>)}
   <text x={(50+plotWidth-20)/2} y="218" textAnchor="middle">{t(timed?'Time (seconds)':'Observation index')}</text>
  </svg></div><label className="field">{t('Inspect observation')}<select value={selected.id} onChange={event=>setPointId(event.target.value)}>{points.map(p=><option key={p.id} value={p.id}>{p.id} · {p.value}{timed?` · ${p.time!/1000}s`:''}</option>)}</select></label>
  <p className="d5-v-caption">{t('Points are saved observations only. Gaps are not interpolated; raw scores are not universal authenticity probabilities.')}</p>
 </section>;
}

export function ReportTimeline({report}:{report:ReportData}){
 const milestones=reportMilestones(report);
 return <section className="d5-milestone-section"><h3><Clock3 size={17}/>{t('Recorded examination timeline')}</h3><ol className="d5-milestones">{milestones.map(row=><li key={row.id}><time dateTime={row.time}>{utc(row.time)} {t('UTC')}</time><b>{t(row.label)}</b><small>{row.actor} · {t('self-declared')}</small></li>)}</ol><p className="d5-v-caption">{t('Recorded milestones only; the full audit summary retains its scope and truncation status.')}</p></section>;
}

export function ReportVisualDashboard({report}:{report:ReportData}){
 const [selected,setSelected]=useState(report.evidence[0]?.evidence_id??'');
 const model=reportVisualModel(report),active=report.evidence.find(e=>e.evidence_id===selected)??report.evidence[0];
 return <div className="d5-dashboard-view"><div className="d5-dashboard-title"><Layers size={22}/><div><span className="d5-kicker">{t('SAVED REPORT INTELLIGENCE')}</span><h2>{report.case.title}</h2><p>{report.case.id} · {t('Revision')} {report.revision} · {t('Snapshot data only')}</p></div></div>
  <ReportVisualSummary report={report}/>
  <div className="d5-visual-columns"><div><EvidenceMap report={report} selected={active?.evidence_id??''} onSelect={setSelected}/>{report.evidence.length>0&&<label className="field d5-evidence-picker">{t('Evidence to inspect')}<select value={active?.evidence_id??''} onChange={e=>setSelected(e.target.value)}>{report.evidence.map(e=><option key={e.evidence_id} value={e.evidence_id}>{e.evidence_id} · {e.filename}</option>)}</select></label>}</div><SavedScorePlot report={report} evidenceId={active?.evidence_id??''}/></div>
  <section className="d5-v-panel"><div className="d5-v-heading"><h3>{t('Evidence × examination channel')}</h3><span>{t('Full saved inventory')}</span></div><div className="d5-matrix-wrap"><table className="d5-visual-matrix"><thead><tr><th>{t('Evidence')}</th>{channels.map(c=><th key={c.key}>{t(c.short)}</th>)}</tr></thead><tbody>{model.matrix.map(row=><tr key={row.evidence.evidence_id}><th scope="row"><button onClick={()=>setSelected(row.evidence.evidence_id)} aria-pressed={active?.evidence_id===row.evidence.evidence_id}>{row.evidence.media_type==='video'?<Film size={16}/>:row.evidence.media_type==='audio'?<AudioLines size={16}/>:<FileImage size={16}/>}<span>{row.evidence.evidence_id}<small>{row.evidence.filename}</small></span></button></th>{row.cells.map(cell=><td key={cell.channel}><span className={'d5-cell-state d5-cell-'+cell.state}>{t(stateLabels[cell.state])}</span><small>{[...new Set(cell.findings.map(classification))].map(label=>t(label)).join(' · ')||t('Not assessed in report scope')}</small></td>)}</tr>)}</tbody></table></div></section>
  <div className="d5-v-panel"><ReportTimeline report={report}/></div>
 </div>;
}
