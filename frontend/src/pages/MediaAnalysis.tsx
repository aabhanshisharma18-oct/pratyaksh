import {useState} from 'react';
import {DetectionLab} from './DetectionLab';
import {ArrowRight,FileAudio,FileImage,FileVideo,Plus,ScanSearch,ShieldCheck} from 'lucide-react';
import {channels,classification,type CaseRecord,type Evidence,type Finding} from '../model';
import './media-analysis.css';

const icon={image:FileImage,audio:FileAudio,video:FileVideo};
type Props={baseUrl:string;cases:CaseRecord[];activeCase?:CaseRecord;evidence:Evidence[];findings:Finding[];onCase:(id:string)=>void;onOpen:(evidence:Evidence)=>void;onAdd:()=>void};

export function MediaAnalysis({baseUrl,cases,activeCase,evidence,findings,onCase,onOpen,onAdd}:Props){
 const [showCaseEvidence,setShowCaseEvidence]=useState(false);
 const viewSwitch=<div className="button-row" role="group" aria-label="Media Analysis view">
   <button type="button" className="button secondary" aria-pressed={!showCaseEvidence} onClick={()=>setShowCaseEvidence(false)}>Media tools</button>
   <button type="button" className="button secondary" aria-pressed={showCaseEvidence} onClick={()=>setShowCaseEvidence(true)}>Case evidence</button>
 </div>;

 return <div className="media-analysis-page"><header className="media-analysis-hero"><div><h1>Media Analysis</h1></div><div>{viewSwitch}{showCaseEvidence&&<label>Investigation<select value={activeCase?.id||''} onChange={event=>onCase(event.target.value)}><option value="">Select a case</option>{cases.map(item=><option key={item.id} value={item.id}>{item.id} · {item.title}</option>)}</select></label>}</div></header>
 <div hidden={showCaseEvidence}><DetectionLab baseUrl={baseUrl} embedded/></div>
 {showCaseEvidence&&<>
 {!activeCase?<section className="panel media-analysis-empty"><ScanSearch size={30}/><h2>Select an investigation</h2></section>:<><section className="analysis-separation-notice"><ShieldCheck size={19}/><div><strong>Each check has its own result.</strong></div></section><div className="analysis-toolbar"><div><strong>{activeCase.title}</strong><span>{evidence.length} evidence item{evidence.length===1?'':'s'}</span></div><button className="button primary" onClick={onAdd}><Plus size={14}/>Add evidence</button></div>{!evidence.length?<section className="panel media-analysis-empty"><FileImage size={30}/><h2>No evidence to analyse</h2><button className="button primary" onClick={onAdd}>Add evidence</button></section>:<section className="analysis-evidence-grid">{evidence.map(item=>{const Icon=icon[item.type],records=findings.filter(finding=>finding.evidence_id===item.id);return <article className="panel" key={item.id}><header><span className={`analysis-file-icon ${item.type}`}><Icon size={18}/></span><div><strong>{item.name}</strong><small>{item.id} · {item.type}</small></div></header><div className="analysis-channel-list">{channels.map(channel=>{const latest=records.filter(finding=>finding.category===channel.key).at(-1);return <div key={channel.key}><span>{channel.name}</span><b>{latest?classification(latest):'Not examined'}</b></div>})}</div><button className="button secondary full" onClick={()=>onOpen(item)}>{records.length?'Review analysis':'Open evidence'}<ArrowRight size={13}/></button></article>})}</section>}</>}
 </>}
 </div>;
}
