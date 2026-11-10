import React,{useMemo,useState} from 'react';
import {ArrowUpRight,Check,Copy,FileImage,Film,AudioLines,GitBranch,FileText,Layers} from 'lucide-react';
import {channels,classification,Evidence,Finding,tone} from '../model';

type SortKey='name'|'type'|'added';
type Props={
  evidence:Evidence[];
  findings:Finding[];
  onOpen:(evidence:Evidence)=>void;
  onProvenance:(evidence:Evidence)=>void;
  onReports:()=>void;
  onAdd:()=>void;
};

const iconFor=(type:Evidence['type'])=>type==='video'?Film:type==='audio'?AudioLines:FileImage;
const parsedDate=(value:string)=>{const time=Date.parse(value);return Number.isNaN(time)?0:time};
export function formatReceived(value:string):string{
  const time=parsedDate(value);
  if(!time)return value;
  return new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeStyle:'short',timeZone:'UTC'}).format(new Date(time))+' UTC';
}

function ChannelState({findings}:{findings:Finding[]}){
  if(!findings.length)return <span className="channel-state neutral"><i/>Not examined</span>;
  const finding=findings[findings.length-1];
  return <span className={`channel-state ${tone(finding)}`}><i/>{classification(finding)}</span>;
}

export function EvidenceTable({evidence,findings,onOpen,onProvenance,onReports,onAdd}:Props){
  const [sort,setSort]=useState<SortKey>('added');
  const [ascending,setAscending]=useState(false);
  const [selected,setSelected]=useState<Set<string>>(new Set());
  const sorted=useMemo(()=>[...evidence].sort((a,b)=>{
    const result=sort==='added'?parsedDate(a.received)-parsedDate(b.received):a[sort].localeCompare(b[sort]);
    return ascending?result:-result;
  }),[evidence,sort,ascending]);
  const chooseSort=(next:SortKey)=>{if(sort===next)setAscending(value=>!value);else{setSort(next);setAscending(true)}};
  const allSelected=sorted.length>0&&sorted.every(item=>selected.has(item.id));
  const toggleAll=()=>setSelected(allSelected?new Set():new Set(sorted.map(item=>item.id)));
  const toggle=(id:string)=>setSelected(current=>{const next=new Set(current);if(next.has(id))next.delete(id);else next.add(id);return next});
  if(!sorted.length)return <div className="empty"><Layers size={30}/><h3>No evidence found</h3><p>Add evidence or try another search.</p><button className="button primary" onClick={onAdd}>Add evidence</button></div>;
  return <>
    <div className="table-scroll"><table className="evidence-table"><thead><tr><th className="checkcell"><input type="checkbox" aria-label="Select all evidence" checked={allSelected} onChange={toggleAll}/></th><th><button className="sort-button" onClick={()=>chooseSort('name')}>Evidence name {sort==='name'&&(ascending?'↑':'↓')}</button></th><th><button className="sort-button" onClick={()=>chooseSort('type')}>Type {sort==='type'&&(ascending?'↑':'↓')}</button></th><th>Four-channel review</th><th>SHA-256</th><th><button className="sort-button" onClick={()=>chooseSort('added')}>Added {sort==='added'&&(ascending?'↑':'↓')}</button></th><th>Links</th></tr></thead><tbody>{sorted.map(item=>{const Icon=iconFor(item.type);return <tr key={item.id}><td className="checkcell"><input type="checkbox" aria-label={`Select ${item.name}`} checked={selected.has(item.id)} onChange={()=>toggle(item.id)}/></td><td><button className="file-name" onClick={()=>onOpen(item)}><span className={`evidence-icon ${item.type}`}><Icon size={17}/></span><span><strong>{item.name}</strong><small><span className="mono">{item.id}</span> / {item.role}{item.fixture&&<span className="tiny-fixture">FIXTURE</span>}</small></span></button></td><td><span className="type-tag">{item.type.toUpperCase()}</span><small className="subtext">{item.size}</small></td><td><div className="matrix-dots expanded">{channels.map(channel=><ChannelState key={channel.key} findings={findings.filter(finding=>finding.evidence_id===item.id&&finding.category===channel.key)}/>)}</div></td><td><button className="hash-chip mono" title={item.hash} onClick={()=>navigator.clipboard.writeText(item.hash)}>{item.hash.slice(0,8)}…<Copy size={12}/></button></td><td><time dateTime={item.received}>{formatReceived(item.received)}</time></td><td><div className="evidence-links"><button onClick={()=>onProvenance(item)}><GitBranch size={14}/>Provenance</button><button onClick={onReports}><FileText size={14}/>Reports</button><button className="icon-button" aria-label={`Open ${item.name}`} onClick={()=>onOpen(item)}><ArrowUpRight size={16}/></button></div></td></tr>})}</tbody></table></div>
    <div className="evidence-cards">{sorted.map(item=>{const Icon=iconFor(item.type);return <article key={item.id}><label><input type="checkbox" checked={selected.has(item.id)} onChange={()=>toggle(item.id)}/><span>Select</span></label><button className="card-open" onClick={()=>onOpen(item)}><Icon size={19}/><span><strong>{item.name}</strong><small>{item.id} · {item.type.toUpperCase()}</small></span><ArrowUpRight size={16}/></button><time>{formatReceived(item.received)}</time><div className="mobile-channel-list">{channels.map(channel=><ChannelState key={channel.key} findings={findings.filter(finding=>finding.evidence_id===item.id&&finding.category===channel.key)}/>)}</div><div className="evidence-links"><button onClick={()=>onProvenance(item)}><GitBranch size={14}/>Provenance</button><button onClick={onReports}><FileText size={14}/>Reports</button></div></article>})}</div>
  </>;
}
