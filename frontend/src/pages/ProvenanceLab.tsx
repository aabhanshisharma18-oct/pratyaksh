import {translate,useFormatters,useI18n} from '../i18n';
import {PageHeading} from '../components/PageHeading';
import {useEffect,useRef,useState,type PointerEvent} from 'react';
import type {Evidence} from '../model';
import {caseOriginalUrl} from '../data/caseSource';
import {Download,FileImage,Film,AudioLines,Grip,GitBranch,Hash,Loader2,Plus,Printer,Search,Upload,X} from 'lucide-react';
import {analyzeProvenance,provenanceEndpoint,provenanceRequest,provenanceReportSchema,latestCaseProvenance,type ProvenanceImage,type ProvenanceRelationship,type ProvenanceReport} from '../data/provenance';
import {ReactFlow,Background,Controls,Handle,Position,BaseEdge,EdgeLabelRenderer,MiniMap,useReactFlow,type EdgeProps,type NodeProps,type XYPosition} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './provenance.css';
import {proposePhotoArea} from './photoAreaProposal';

type LocalImage = {file:File;url:string;area?:Region};
type Region = [number,number,number,number];

function ImagePreview({src,name,region,area,points,mediaType,timestamp}: {
  src:string;name:string;region?:Region;area?:Region;points?:[number,number][];mediaType?:string;timestamp?:number;
}) {
  if(mediaType==='video')return <video controls preload="metadata" style={{width:'100%'}} src={timestamp===undefined?src:src+'#t='+timestamp/1000} aria-label={name}/>;
  if(mediaType==='audio')return <audio controls src={src} aria-label={name}/>;
  return <div className="provenance-preview">
    <img src={src} alt={name}/>
    {area&&<AreaBox area={area}/>}
    {points?.map(([x,y],index)=><span key={index} className="provenance-match-point"
      style={{left:x*100+'%',top:y*100+'%'}} title={'Match '+(index+1)}/>)}
    {region&&<span className="provenance-match-region" style={{
      left:region[0]*100+'%',top:region[1]*100+'%',
      width:(region[2]-region[0])*100+'%',height:(region[3]-region[1])*100+'%',
    }}/>}
  </div>;
}

function AreaBox({area,proposed=false}: {area:Region;proposed?:boolean}) {
  const [x0,y0,x1,y1]=area;
  return <span className={proposed?"provenance-selected-area provenance-proposal":"provenance-selected-area"} style={{
    left:x0*100+'%',top:y0*100+'%',width:(x1-x0)*100+'%',height:(y1-y0)*100+'%',
  }}/>;
}

function PhotoAreaPicker({item,onChange,disabled,baseUrl}: {item:{file?:File;name:string;url:string;area?:Region};onChange:(area?:Region)=>void;disabled:boolean;baseUrl:string}) {
  const start=useRef<[number,number]|null>(null);
  const [draft,setDraft]=useState<Region>();
  const [proposal,setProposal]=useState<Region>();
  const [proposalMessage,setProposalMessage]=useState('');
  const imageRef=useRef<HTMLImageElement>(null);
  const [ready,setReady]=useState(false);
  const [useServerPreview,setUseServerPreview]=useState(/\.hei[cf]$/i.test(item.file?.name||''));
  const [previewUrl,setPreviewUrl]=useState('');
  const [previewError,setPreviewError]=useState('');
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    if(!useServerPreview||!item.file)return;
    const controller=new AbortController();
    const timeout=window.setTimeout(()=>controller.abort(new Error('Preview timed out.')),15000);
    let disposed=false;
    let objectUrl='';
    setPreviewUrl('');setPreviewError('');setReady(false);
    const body=new FormData();
    body.set('file',item.file);
    async function loadPreview() {
      try {
        const response=await provenanceRequest(baseUrl,'/preview',{method:'POST',body,signal:controller.signal});
        const blob=await response.blob();
        if(!disposed){
          objectUrl=URL.createObjectURL(blob);
          setPreviewUrl(objectUrl);
        }
      } catch(error) {
        if(!disposed)setPreviewError(error instanceof Error?error.message:'Preview could not be loaded.');
      } finally {window.clearTimeout(timeout)}
    }
    void loadPreview();
    return ()=>{
      disposed=true;
      controller.abort();
      window.clearTimeout(timeout);
      if(objectUrl)URL.revokeObjectURL(objectUrl);
    };
  },[baseUrl,item.file,useServerPreview,retry]);
  const src=useServerPreview?previewUrl:item.url;
  function rectangle(event:PointerEvent<HTMLDivElement>):Region {
    const bounds=event.currentTarget.getBoundingClientRect();
    const x=Math.min(1,Math.max(0,(event.clientX-bounds.left)/bounds.width));
    const y=Math.min(1,Math.max(0,(event.clientY-bounds.top)/bounds.height));
    const [a,b]=start.current??[x,y];
    return [Math.min(a,x),Math.min(b,y),Math.max(a,x),Math.max(b,y)];
  }
  return <section className="panel provenance-area-picker">
    <h2>{translate("Select photo area")}</h2>
    <p>{translate("Drag around the photo to exclude screenshot headers and buttons. The original file stays intact.")}</p>
    <div className="provenance-area-canvas" onPointerDown={event=>{
      if(disabled||!ready||event.button!==0||!event.isPrimary)return;
      const [x,y]=rectangle(event);
      setProposal(undefined);setProposalMessage('');
      start.current=[x,y];setDraft([x,y,x,y]);
      event.currentTarget.setPointerCapture(event.pointerId);
    }} onPointerMove={event=>{if(start.current&&event.isPrimary)setDraft(rectangle(event))}}
      onPointerCancel={()=>{start.current=null;setDraft(undefined)}}
      onPointerUp={event=>{
        if(!start.current||!event.isPrimary)return;
        const area=rectangle(event);start.current=null;setDraft(undefined);
        if(area[2]-area[0]>=.04&&area[3]-area[1]>=.04)onChange(area);
      }}>
      {src&&<img ref={imageRef} src={src} alt={item.name} draggable={false} crossOrigin={item.file?undefined:"anonymous"} onLoad={()=>setReady(true)} onError={()=>{
        setReady(false);
        if(useServerPreview||!item.file)setPreviewError('The generated preview could not be displayed.');
        else setUseServerPreview(true);
      }}/>}
      {(draft||item.area)&&<AreaBox area={(draft||item.area)!}/>}
      {proposal&&<AreaBox area={proposal} proposed/>}
    </div>
    {useServerPreview&&!ready&&!previewError&&<p role="status">{translate("Preparing image preview…")}</p>}
    {previewError&&<div role="status">
      <p>{previewError}</p>
      <button className="button secondary" disabled={disabled} onClick={()=>setRetry(value=>value+1)}>{translate("Retry preview")}</button>
    </div>}
    <p>{item.area?'Selected photo area will be compared.':'Whole image selected.'}</p>
    <div className="provenance-actions">
      <button className="button secondary" disabled={disabled||!ready} onClick={()=>{
        try{
          const next=imageRef.current?proposePhotoArea(imageRef.current):undefined;
          setProposal(next);
          setProposalMessage(next?'Check the blue outline and confirm it if it covers the photo.':'No clear photo area found. Draw a box around the photo.');
        }catch{setProposalMessage('Automatic selection is unavailable for this preview. Draw a box around the photo.')}
      }}>{translate("Suggest photo area")}</button>
      {proposal&&<button className="button primary" disabled={disabled}
        onClick={()=>{onChange(proposal);setProposal(undefined);setProposalMessage('')}}>{translate("Confirm proposed area")}</button>}
      {proposal&&<button className="button secondary" disabled={disabled}
        onClick={()=>{setProposal(undefined);setProposalMessage('')}}>{translate("Discard proposal")}</button>}
    </div>
    {proposalMessage&&<p role="status">{proposalMessage}</p>}
    <button className="button secondary" disabled={disabled||!item.area} onClick={()=>onChange(undefined)}>{translate("Use whole image")}</button>
  </section>;
}

const connectionLabels:Record<string,string> = {
  exact_copy:'Exact hash match',matching_content:'Possible region relation',
  shared_metadata:'Agreeing metadata',shared_credentials:'Shared credential record',
};
const edgeStyles:Record<string,{color:string;dash?:string;label:string}> = {
  exact_copy:{color:'#008d7f',label:'Exact copy'},
  matching_content:{color:'#3974cc',label:'Shared region'},
  shared_metadata:{color:'#b46e17',dash:'7 5',label:'Metadata clue'},
  shared_credentials:{color:'#8c5abb',dash:'2 5',label:'Credential record'},
};
function linkProof(edge:ProvenanceRelationship) {
  if(edge.kind==='exact_copy')return 'Identical SHA-256';
  if(edge.support)return edge.support.matched_features+' aligned points';
  if(edge.metadata_fields){
    const count=Object.keys(edge.metadata_fields).length;
    return count+(count===1?' field agrees':' fields agree');
  }
  return 'Matching credential record';
}
const ports = {left:Position.Left,right:Position.Right,top:Position.Top,bottom:Position.Bottom};

function FileNode({data}:NodeProps) {
  const Icon=data.mediaType==='video'?Film:data.mediaType==='audio'?AudioLines:FileImage;
  return <div className={'provenance-flow-node'+(data.focused?' focused':'')+(data.dimmed?' dimmed':'')}>
    {Object.entries(ports).flatMap(([key,position])=>[
      <Handle key={key+'-in'} id={key+'-in'} type="target" position={position}/>,
      <Handle key={key+'-out'} id={key+'-out'} type="source" position={position}/>,
    ])}
    <div className="provenance-node-image">
      <Icon size={30}/>{typeof data.preview==='string'&&<img src={String(data.preview)} alt="" draggable={false} onError={event=>{event.currentTarget.hidden=true;}}/>}
      <span className="provenance-node-id">{String(data.imageId)}</span><Grip className="provenance-node-grip" size={17} aria-hidden="true"/>
    </div>
    <div className="provenance-node-caption">
      <strong title={String(data.filename)}>{String(data.filename)}</strong>
      <small>{String(data.mediaLabel)} · {data.count?String(data.count)+(data.count===1?' link':' links'):'No links shown'}</small>
    </div>
  </div>;
}
const nodeTypes={file:FileNode};

function ConnectionEdge({id,sourceX,sourceY,targetX,targetY,style,data,selected}:EdgeProps) {
  const dx=targetX-sourceX,dy=targetY-sourceY,length=Math.max(1,Math.hypot(dx,dy));
  const offset=Number(data?.offset||0);
  const middleX=(sourceX+targetX)/2;
  const middleY=(sourceY+targetY)/2;
  const controlX=middleX-dy/length*offset;
  const controlY=middleY+dx/length*offset;
  const path=`M ${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`;
  const labelX=(middleX+controlX)/2;
  const labelY=(middleY+controlY)/2;
  return <>
    <BaseEdge id={id} path={path} style={style} interactionWidth={22}/>
    {(selected||data?.showLabel)&&<EdgeLabelRenderer><button type="button"
      className={'provenance-edge-label nodrag nopan'+(selected?' active':'')}
      style={{transform:`translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,borderColor:String(style?.stroke),color:String(style?.stroke)}}
      onClick={()=>{const select=data?.onSelect;if(typeof select==='function')select(id)}}
      aria-label={String(data?.accessibleLabel)} aria-pressed={Boolean(selected)}><strong>{String(data?.label)}</strong><small>{String(data?.proof)}</small></button></EdgeLabelRenderer>}
  </>;
}
const edgeTypes={connection:ConnectionEdge};

function MapFit({resetKey}:{resetKey:number}) {
  const {fitView}=useReactFlow();
  useEffect(()=>{
    const frame=requestAnimationFrame(()=>void fitView({padding:0.14,maxZoom:1}));
    return()=>cancelAnimationFrame(frame);
  },[fitView,resetKey]);
  return null;
}

function RelationshipGraph({report,onSelect,selected,onFile,filter,activeImage,imageUrl}: {
  report:ProvenanceReport;onSelect:(id:string)=>void;selected:string|null;onFile:(index:number)=>void;filter:string;
  activeImage:number;imageUrl:(image:ProvenanceImage)=>string;
}) {
  const [positions,setPositions]=useState<Record<string,XYPosition>>({});
  const [resetKey,setResetKey]=useState(0);
  const visible=report.relationships.filter(edge=>filter==='all'||edge.kind===filter);
  const focus=visible.find(edge=>edge.id===selected);
  const imageCount=report.images.length;
  const radiusX=Math.max(255,imageCount*37);
  const radiusY=Math.max(150,imageCount*25);
  const nodes=report.images.map((image,index)=>{
    const angle=2*Math.PI*index/imageCount-Math.PI/2;
    const position=positions[image.id]??(imageCount===2?{x:index*360,y:0}:
      {x:Math.round(radiusX*Math.cos(angle)),y:Math.round(radiusY*Math.sin(angle))});
    const focused=focus?(focus.left_id===image.id||focus.right_id===image.id):index===activeImage;
    const mediaLabel=image.media_type==='video'?'Video':image.media_type==='audio'?'Audio':'Image';
    return {id:image.id,type:'file',position,ariaLabel:'Inspect '+image.filename,
      data:{imageId:image.id,filename:image.filename,mediaType:image.media_type,mediaLabel,
        preview:!image.media_type||image.media_type==='image'?imageUrl(image):undefined,
        focused,dimmed:Boolean(focus&&!focused),
        count:visible.filter(edge=>edge.left_id===image.id||edge.right_id===image.id).length}};
  });
  const byId=new Map(nodes.map(node=>[node.id,node]));
  const edges=visible.flatMap(edge=>{
    const source=byId.get(edge.left_id),target=byId.get(edge.right_id);
    if(!source||!target)return [];
    const dx=target.position.x-source.position.x,dy=target.position.y-source.position.y;
    const horizontal=Math.abs(dx)>=Math.abs(dy);
    const from=horizontal?(dx>=0?'right':'left'):(dy>=0?'bottom':'top');
    const to=horizontal?(dx>=0?'left':'right'):(dy>=0?'top':'bottom');
    const parallel=visible.filter(item=>item.left_id===edge.left_id&&item.right_id===edge.right_id);
    const offset=(parallel.findIndex(item=>item.id===edge.id)-(parallel.length-1)/2)*76;
    const {color,dash,label}=edgeStyles[edge.kind];
    const edgeLabel=edge.support?.frame_timestamps_ms?'Video match':label;
    const accessibleLabel=edgeLabel+': '+source.data.filename+' and '+target.data.filename;
    return [{id:edge.id,source:edge.left_id,target:edge.right_id,sourceHandle:from+'-out',targetHandle:to+'-in',
      ariaLabel:accessibleLabel,type:'connection',data:{offset,label:edgeLabel,proof:linkProof(edge),accessibleLabel,onSelect,showLabel:!focus&&visible.length<=10&&(parallel.length===1||parallel[0].id===edge.id)},
      style:{stroke:color,strokeDasharray:dash,strokeWidth:selected===edge.id?4:2.8,opacity:focus&&selected!==edge.id ? 0.32 : 1},
      selected:selected===edge.id,zIndex:selected===edge.id?2:0}];
  });
  return <div className="provenance-flow" aria-label="Interactive relationship map">
    <button type="button" className="button secondary provenance-reset-map"
      onClick={()=>{setPositions({});setResetKey(key=>key+1)}}>Reset layout</button>
    <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} fitView
      minZoom={0.25} maxZoom={2} fitViewOptions={{padding:0.14,maxZoom:1}}
      nodesDraggable nodesConnectable={false} panOnDrag zoomOnScroll={false}
      onNodesChange={changes=>{
        const moves=changes.filter(change=>change.type==='position'&&change.position);
        if(moves.length)setPositions(previous=>{
          const next={...previous};
          for(const change of moves)if(change.type==='position'&&change.position)next[change.id]=change.position;
          return next;
        });
      }}
      onEdgeClick={(_,edge)=>onSelect(edge.id)}
      onNodeClick={(_,node)=>onFile(report.images.findIndex(item=>item.id===node.id))}>
      <MapFit resetKey={resetKey}/>
      <Background gap={22} className="provenance-map-grid"/><Controls showInteractive={false}/>
      {imageCount>=6&&<MiniMap className="provenance-minimap" pannable zoomable ariaLabel="Relationship map overview"/>}
    </ReactFlow>
  </div>;
}

export function ProvenanceLab({baseUrl,initialCaseId,initialAnalysisId,initialRelationshipId,caseEvidence}: {baseUrl:string;initialCaseId?:string;initialAnalysisId?:string;initialRelationshipId?:string;caseEvidence?:Evidence[]}) {
  const {language}=useI18n();
  const {formatDate}=useFormatters();
  const [selectedCaseIds,setSelectedCaseIds]=useState<string[]>([]);
  const [caseAreas,setCaseAreas]=useState<Record<string,Region|undefined>>({});
  const [casePreviewId,setCasePreviewId]=useState('');
  const casePreview=caseEvidence?.find(item=>item.id===casePreviewId&&selectedCaseIds.includes(item.id)&&item.type==='image');
  const [images,setImages]=useState<LocalImage[]>([]);
  const [adding,setAdding]=useState(false);
  const [pendingIndex,setPendingIndex]=useState(0);
  const [report,setReport]=useState<ProvenanceReport|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [selected,setSelected]=useState<string|null>(null);
  const [activeImage,setActiveImage]=useState(0);
  const [showRegions,setShowRegions]=useState(true);
  const [caseId,setCaseId]=useState(initialCaseId||'PROV-DEMO');
  const [caseTitle,setCaseTitle]=useState('Media relationship examination');
  const [analyst,setAnalyst]=useState('Local analyst');
  const [verification,setVerification]=useState<any>(null);
  const [audit,setAudit]=useState<any>(null);
  const [history,setHistory]=useState<{id:string;created_at:string}[]>([]);
  const [working,setWorking]=useState('');
  const [showDifference,setShowDifference]=useState(false);
  const [retainedAnchor,setRetainedAnchor]=useState('');
  const [packageAnchor,setPackageAnchor]=useState('');
  const [filter,setFilter]=useState('all');
  const [pairBudget,setPairBudget]=useState('all');
  const [reviewText,setReviewText]=useState('');
  const [reviewScope,setReviewScope]=useState('');
  const [lastAnalysis,setLastAnalysis]=useState(()=>{try{return localStorage.getItem('pratyaksh.provenance.last')||''}catch{return ''}});
  const locked=useRef(false);
  const addInput=useRef<HTMLInputElement>(null);
  useEffect(()=>{
    setCaseTitle(value=>['Media relationship examination','मीडिया संबंध परीक्षण'].includes(value)?translate('Media relationship examination'):value);
    setAnalyst(value=>['Local analyst','स्थानीय विश्लेषक'].includes(value)?translate('Local analyst'):value);
  },[language]);
  useEffect(()=>{setPackageAnchor('');if(report){setLastAnalysis(report.analysis_id);try{localStorage.setItem('pratyaksh.provenance.last',report.analysis_id)}catch{/* storage can be disabled */}}},[report]);
  const verifyInput=useRef<HTMLInputElement>(null);
  const input=useRef<HTMLInputElement>(null);
  const urls=useRef<string[]>([]);
  const request=useRef<AbortController|null>(null);
  useEffect(()=>{
    if(!initialCaseId||!baseUrl)return;
    const controller=new AbortController();
    const load=initialAnalysisId
      ? provenanceRequest(baseUrl,'/reports/'+encodeURIComponent(initialAnalysisId),{signal:controller.signal}).then(response=>response.json()).then(value=>provenanceReportSchema.parse(value))
      : latestCaseProvenance(baseUrl,initialCaseId,controller.signal);
    void load.then(saved=>{
      if(saved&&!controller.signal.aborted&&!locked.current){
        if(saved.case.id!==initialCaseId)throw new Error('The saved comparison belongs to a different case.');
        if(initialRelationshipId&&!saved.relationships.some(edge=>edge.id===initialRelationshipId))throw new Error('The cited comparison is unavailable in this saved report.');
        setReport(saved);
        setSelected(initialRelationshipId||saved.relationships[0]?.id||null);
        setShowRegions(true);
        setCaseTitle(saved.case.title);
      }
    }).catch(error=>{if(!controller.signal.aborted)setError(error.message)});
    return ()=>controller.abort();
  },[baseUrl,initialCaseId,initialAnalysisId,initialRelationshipId]);
  const citedComparison=useRef<HTMLElement|null>(null);
  useEffect(()=>{
    if(report&&initialRelationshipId&&selected===initialRelationshipId)citedComparison.current?.scrollIntoView({block:'start'});
  },[report,initialRelationshipId,selected]);
  useEffect(()=>()=>{urls.current.forEach(URL.revokeObjectURL);request.current?.abort()},[]);

  function choose(files:File[], extendReport=false) {
    if(busy||working)return;
    if(files.length+(extendReport?(report?.images.length??0):0)>12){setError('Choose up to 12 images per comparison.');return}
    if(files.some(file=>!file.size||file.size>15*1024*1024)){
      setError('Each image must contain data and be at most 15 MiB.');return;
    }
    if(files.reduce((size,file)=>size+file.size,0)>60*1024*1024){
      setError('Choose a batch up to 60 MiB.');return;
    }
    if(files.some(file=>!['image/jpeg','image/png','image/webp','image/heic','image/heif','audio/wav','audio/x-wav','audio/mpeg','audio/mp3','video/mp4'].includes(file.type)&&!(/\.(?:hei[cf]|mp4)$/i.test(file.name)&&!file.type))){
      setError('Choose JPEG, PNG, WebP, HEIC, WAV, MP3 or MP4 files.');return;
    }
    const next=files.map(file=>images.find(item=>item.file===file)??{file,url:URL.createObjectURL(file)});
    urls.current.filter(url=>!next.some(item=>item.url===url)).forEach(URL.revokeObjectURL);
    urls.current=next.map(item=>item.url);
    setAdding(extendReport);
    setPendingIndex(0);
    if(extendReport){setImages(next);setError('');return}
    setImages(next);setReport(null);setSelected(null);setActiveImage(0);setError('');setVerification(null);setAudit(null);setShowDifference(false);setRetainedAnchor('');setReviewText('');setReviewScope('');setFilter('all');
  }

  async function analyze() {
    if(locked.current)return;
    if(!baseUrl){setError('Start the detection backend and configure its API URL.');return}
    const controller=new AbortController();
    request.current=controller;
    locked.current=true;setBusy(true);setError('');
    try {
      let result:ProvenanceReport;
      if(caseEvidence){
        const response=await provenanceRequest(baseUrl,'/cases/'+encodeURIComponent(caseId)+'/analyze',{
          method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
          body:JSON.stringify({evidence_ids:selectedCaseIds,comparison_areas:selectedCaseIds.map(id=>caseAreas[id]??null),pair_budget:pairBudget==='all'?null:Number(pairBudget)}),
        });
        result=provenanceReportSchema.parse(await response.json());
      }else{
        result=await analyzeProvenance(baseUrl,images.map(item=>item.file),controller.signal,{caseId,title:caseTitle,analyst},images.map(item=>item.area??null),pairBudget==='all'?undefined:Number(pairBudget));
      }
      setReport(result);setSelected(result.relationships[0]?.id??null);setVerification(null);setAudit(null);
    } catch(error) {
      if(!controller.signal.aborted)setError(error instanceof Error?error.message:'The provenance service could not be reached.');
    } finally {locked.current=false;if(!controller.signal.aborted)setBusy(false)}
  }

  async function exportReport() {
    if(!report)return;
    await action('Exporting saved report',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+report.analysis_id+'/export');
      const url=URL.createObjectURL(await response.blob());
      const link=document.createElement('a');link.href=url;link.download=report.analysis_id+'.json';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
  }

  const pair=report?.relationships.find(item=>item.id===selected);
  const frameTimes=pair?.support?.frame_timestamps_ms;
  const left=pair&&report?.images.find(item=>item.id===pair.left_id);
  const right=pair&&report?.images.find(item=>item.id===pair.right_id);
  const source=report?.images[pendingIndex];
  const urlFor=(item:ProvenanceImage)=>item.format==='HEIF'
    ? provenanceEndpoint(baseUrl,'/reports/'+report!.analysis_id+'/images/'+item.id+'/preview')
    : provenanceEndpoint(baseUrl,'/reports/'+report!.analysis_id+'/images/'+item.id);
  const selectPair=(id:string)=>{setSelected(id);setShowDifference(false)};
  const titleFor=(edge:ProvenanceRelationship)=>edge.support?.frame_timestamps_ms?'Sampled video match':connectionLabels[edge.kind];

  async function action(label:string,task:()=>Promise<void>) {
    if(locked.current)return;
    locked.current=true;setWorking(label);setError('');
    try {await task()} catch(error){setError(error instanceof Error?error.message:'The operation failed.')}
    finally {locked.current=false;setWorking('')}
  }
  async function generatePdf() {
    await action('Generating PDF',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+report!.analysis_id+'/pdf',{method:'POST'});
      const url=URL.createObjectURL(await response.blob());
      const link=document.createElement('a');link.href=url;link.download=report!.analysis_id+'.pdf';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
  }
  async function verify() {
    await action('Verifying originals',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+report!.analysis_id+'/verify?retained_anchor='+encodeURIComponent(retainedAnchor.trim()||report!.integrity.anchor_hash),{method:'POST'});
      setVerification(await response.json());
    });
  }
  async function inspectAudit() {
    await action('Reading provenance log',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+report!.analysis_id+'/audit');
      setAudit(await response.json());
    });
  }
  async function runSignals() {
    await action('Running supporting detectors',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+report!.analysis_id+'/images/'+source!.id+'/signals',{method:'POST'});
      setReport(provenanceReportSchema.parse(await response.json()));setVerification(null);setAudit(null);setRetainedAnchor('');
    });
  }
  async function verifyLocal(file:File) {
    await action('Checking supplied original',async()=>{
      const body=new FormData();body.set('file',file);
      const response=await provenanceRequest(baseUrl,'/reports/'+report!.analysis_id+'/images/'+source!.id+'/verify',{method:'POST',body});
      const result=await response.json();
      setVerification({supplied_file:result,filename:file.name});
    });
  }
  async function loadHistory() {
    await action('Loading saved analyses',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports?case_id='+encodeURIComponent(caseId));
      setHistory(await response.json());
    });
  }
  async function restore(id:string) {
    await action('Opening saved analysis',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+id);
      const saved=provenanceReportSchema.parse(await response.json());
      if(caseEvidence&&saved.case.id!==caseId)throw new Error('This analysis belongs to another case.');
      urls.current.forEach(URL.revokeObjectURL);urls.current=[];
      setAdding(false);setImages([]);setReport(saved);setSelected(saved.relationships[0]?.id??null);setActiveImage(0);
      setCaseTitle(saved.case.title);setAnalyst(saved.case.analyst);setCaseId(saved.case.id);
      setVerification(null);setAudit(null);setShowDifference(false);setRetainedAnchor('');setReviewScope('');setReviewText('');setFilter('all');
    });
  }
  async function extend() {
    if(!images.length||!report)return;
    await action('Adding files and recomparing',async()=>{
      const body=new FormData();
      images.forEach(item=>body.append('files',item.file));
      body.set('comparison_areas',JSON.stringify(images.map(item=>item.area??null)));
      const response=await provenanceRequest(baseUrl,'/reports/'+report.analysis_id+'/extend',{method:'POST',body});
      const saved=provenanceReportSchema.parse(await response.json());
      urls.current.forEach(URL.revokeObjectURL);urls.current=[];setImages([]);setAdding(false);
      setReport(saved);setSelected(saved.relationships[0]?.id??null);setShowDifference(false);
      setVerification(null);setAudit(null);setRetainedAnchor('');setReviewScope('');
    });
  }
  async function saveReview() {
    if(!report||!reviewText.trim())return;
    await action('Saving reviewer interpretation',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+report.analysis_id+'/notes',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({author:analyst,text:reviewText,scope_id:reviewScope||null})});
      setReport(provenanceReportSchema.parse(await response.json()));setReviewText('');setVerification(null);setAudit(null);setRetainedAnchor('');
    });
  }
  async function downloadBundle() {
    if(!report)return;
    await action('Preparing verified evidence package',async()=>{
      const response=await provenanceRequest(baseUrl,'/reports/'+report.analysis_id+'/bundle',{method:'POST'});
      setPackageAnchor(response.headers.get('X-Manifest-SHA256')||'');
      const url=URL.createObjectURL(await response.blob());
      const link=document.createElement('a');link.href=url;link.download=report.analysis_id+'-evidence.zip';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
  }
  const visibleRelationships=report?.relationships.filter(edge=>filter==='all'||edge.kind===filter)||[];
  const unconnected=report?.images.filter(image=>!report.relationships.some(edge=>(edge.kind==='exact_copy'||edge.kind==='matching_content')&&(edge.left_id===image.id||edge.right_id===image.id)))||[];
  const unmatchedPairs=(report?.visual_matching_available?report.images:[]).flatMap((left,index)=>
    report!.images.slice(index+1).filter(right=>left.media_type===right.media_type&&left.media_type!=='audio'&&
      !report!.relationships.some(edge=>edge.left_id===left.id&&edge.right_id===right.id&&
        (edge.kind==='matching_content'||edge.kind==='exact_copy')))
      .map(right=>({left,right})));
  return <div className="provenance-lab">
    <PageHeading eyebrow="EXAMINATION" title="Provenance & Source Attribution"
      subtitle="Compare files and inspect their links." className="provenance-heading">
      {report&&<div className="provenance-actions">
        <button className="button primary" disabled={busy||!!working} onClick={generatePdf}><Printer size={15}/>{translate("Generate PDF report")}</button>
        <button className="button secondary" disabled={busy||!!working} onClick={exportReport}><Download size={15}/>{translate("Export JSON")}</button>
        <button className="button secondary" disabled={busy||!!working} onClick={downloadBundle}><Download size={15}/>{translate("Evidence package")}</button>
      </div>}
    </PageHeading>

    <section className="panel provenance-case" aria-label={translate("Provenance case context")}>
      <label>{translate("Case ID")}<input value={caseId} maxLength={100} disabled={!!caseEvidence||busy||!!working} onChange={event=>{setCaseId(event.target.value);setHistory([])}}/></label>
      <label>{translate("Case title")}<input value={caseTitle} maxLength={200} disabled={busy||!!working} onChange={event=>setCaseTitle(event.target.value)}/></label>
      <label>{translate("Analyst (self-declared)")}<input value={analyst} maxLength={100} disabled={busy||!!working} onChange={event=>setAnalyst(event.target.value)}/></label>
      <button className="button secondary" disabled={busy||!!working||!caseId} onClick={loadHistory}>{translate("Saved analyses")}</button>
    </section>
    {history.length>0&&<div className="provenance-history">{history.map(item=><button className="button secondary" key={item.id} disabled={busy||!!working} onClick={()=>restore(item.id)}>{item.id.slice(0,14)} · {formatDate(item.created_at)}</button>)}</div>}
    {!caseEvidence&&!report&&lastAnalysis&&<p className="provenance-resume"><button className="button secondary" disabled={busy||!!working} onClick={()=>restore(lastAnalysis)}>{translate("Resume last saved analysis")}</button></p>}
    {caseEvidence?<section className="panel provenance-area-picker">
      <h2>{translate("Preserved case evidence")}</h2>
      <p>{translate("Select at least two files. For screenshots, select the photo area.")}</p>
      {caseEvidence.length===0&&<p>{translate("Add evidence to this case to start a comparison.")}</p>}
      {caseEvidence.map(item=><div className="provenance-actions" key={item.id}>
        <label><input type="checkbox" checked={selectedCaseIds.includes(item.id)} disabled={busy||!!working}
          onChange={event=>setSelectedCaseIds(ids=>event.target.checked?[...ids,item.id]:ids.filter(id=>id!==item.id))}/>
          {item.id} · {item.name}
        </label>
        {item.type==='image'&&selectedCaseIds.includes(item.id)&&<button className="button secondary"
          disabled={busy||!!working} onClick={()=>setCasePreviewId(item.id)}>{translate(caseAreas[item.id]?'Edit photo area':'Select photo area')}</button>}
      </div>)}
      {casePreview&&<PhotoAreaPicker key={casePreview.id} baseUrl={baseUrl} disabled={busy||!!working}
        item={{name:casePreview.name,url:caseOriginalUrl(caseId,casePreview.id,true),area:caseAreas[casePreview.id]}}
        onChange={area=>setCaseAreas(areas=>({...areas,[casePreview.id]:area}))}/>}
      <button className="button primary" disabled={selectedCaseIds.length<2||selectedCaseIds.length>12||busy||!!working}
        onClick={analyze}>{translate(busy?'Comparing files…':'Analyze relationships')}</button>
    </section>:<section className="provenance-intake panel" aria-label={translate("Image comparison intake")}>
      <input ref={input} type="file" accept=".jpg,.jpeg,.png,.webp,.heic,.heif,.wav,.mp3,.mp4" multiple hidden
        disabled={busy||!!working} onChange={event=>{choose(Array.from(event.target.files||[]));event.target.value=''}}/>
      <button className="provenance-drop" disabled={busy||!!working} onClick={()=>input.current?.click()}
        onDragOver={event=>event.preventDefault()}
        onDrop={event=>{event.preventDefault();choose(Array.from(event.dataTransfer.files))}}>
        <Upload size={23}/><span><strong>{translate(report?'Start a new comparison':images.length?'Choose another media set':'Choose media files to compare')}</strong>
          <small>{translate("2–12 files · JPEG, PNG, WebP, HEIC, WAV, MP3 or MP4 · 15 MiB each, 60 MiB per batch")}</small></span><Plus size={19}/>
      </button>
      <button className="button primary" disabled={busy||!!working||adding||images.length<2||!caseId.trim()||!analyst.trim()} onClick={analyze}>
        {busy?<Loader2 size={16} className="spin"/>:<Search size={16}/>}
        {translate(busy?'Comparing files…':'Analyze relationships')}
      </button>
    </section>}
    <section className="panel" aria-label="Comparison budget">
      <label className="provenance-field">Visual comparison budget
        <select value={pairBudget} disabled={busy||!!working} onChange={event=>setPairBudget(event.target.value)}>
          <option value="all">Compare all eligible pairs</option>
          {[8,16,32,48].map(value=><option key={value} value={value}>CP-SAT · up to {value} pairs</option>)}
        </select>
      </label>
      <details><summary>How the budget works</summary><p>CP-SAT selects pairs for visual checks. Hash and metadata checks still cover every pair.</p></details>
    </section>
    {working&&<p role="status" className="provenance-progress"><Loader2 size={16} className="spin"/>{working}…</p>}
    {packageAnchor&&<section className="panel provenance-verification" role="status"><h2>{translate("Evidence package ready")}</h2>
      <p>{translate("Keep this manifest SHA-256 outside the package, for example in your case handover record:")}</p><p className="mono provenance-hash">{packageAnchor}</p>
      <p>{translate("After extracting the ZIP, run")} <code>{translate("python3 verify.py --expected-manifest")} {packageAnchor}</code>{translate(". The package includes originals, PDF, JSON, activity and the offline verifier.")}</p>
    </section>}
    {error&&<p role="alert" className="provenance-error">{error}</p>}
    {(!report||adding)&&images.length>0&&<section className="provenance-files" aria-label={translate("Selected images")}>
      {images.map((item,index)=><div className={'provenance-file '+(pendingIndex===index?'active':'')} key={item.url}>
        <button onClick={()=>setPendingIndex(index)} aria-pressed={pendingIndex===index}>
          {(item.file.type.startsWith('audio/')||/\.(hei[cf]|mp4)$/i.test(item.file.name))?<FileImage size={30}/>:<img src={item.url} alt=""/>}<span><strong>{item.file.name}</strong><small>{(item.file.size/1024/1024).toFixed(2)} {translate("MiB")}{item.area?' · Photo area selected':''}</small></span>
        </button>
        <button className="icon-button" disabled={busy||!!working} aria-label={'Remove '+item.file.name}
          onClick={()=>choose(images.filter((_,position)=>position!==index).map(image=>image.file),adding)}><X size={14}/></button>
      </div>)}
    </section>}
    {(!report||adding)&&images[pendingIndex]&&!/\.(wav|mp3|mp4)$/i.test(images[pendingIndex].file.name)&&
      <PhotoAreaPicker key={images[pendingIndex].url} item={{...images[pendingIndex],name:images[pendingIndex].file.name}} baseUrl={baseUrl} disabled={busy||!!working}
        onChange={area=>setImages(items=>items.map((item,index)=>index===pendingIndex?{...item,area}:item))}/>}
    {adding&&<div className="provenance-actions">
      <button className="button primary" disabled={!images.length||!!working} onClick={extend}>{translate("Compare added files")}</button>
      <button className="button secondary" disabled={!!working} onClick={()=>{choose([],true);setAdding(false)}}>{translate("Cancel adding files")}</button>
    </div>}
    {!report&&!busy&&<section className="provenance-empty panel">
      <GitBranch size={34}/><h2>{translate(images.length?'Ready to compare':'Follow the connections between files')}</h2>
      <p>{translate("Choose media files to compare")}</p>
      <p>{translate("Source identity and editing order depend on the evidence available in the files.")}</p>
    </section>}
    {busy&&<div role="status" className="provenance-progress"><Loader2 size={18} className="spin"/>{translate("Computing file hashes, reading metadata and matching image features.")}</div>}
    {report&&<>
      <section className="provenance-summary" aria-label={translate("Examination summary")}>
        <div><strong>{report.images.length}</strong><span>{translate("Preserved files")}</span></div>
        <div><strong>{report.exact_duplicate_groups.length}</strong><span>{translate("Exact-copy groups")}</span></div>
        <div><strong>{report.relationships.filter(edge=>edge.kind==='matching_content').length}</strong><span>{translate("Supported visual relations")}</span></div>
        <div><strong>{unconnected.length}</strong><span>{translate("Files without a visual link")}</span></div>
      </section>
      <div className="provenance-actions provenance-add">
        <input ref={addInput} type="file" multiple hidden accept=".jpg,.jpeg,.png,.webp,.heic,.heif,.wav,.mp3" onChange={event=>{choose(Array.from(event.target.files||[]),true);event.target.value=''}}/>
        <button className="button secondary" hidden={!!caseEvidence} disabled={busy||!!working||report.images.length>=12} onClick={()=>addInput.current?.click()}><Plus size={15}/>{translate("Add files to this analysis")}</button>
        <span className="muted small">{translate("Changes create a new saved revision. Earlier analyses remain available.")}</span>
      </div>
      <section className="provenance-files" aria-label={translate("Preserved files")}>
        {report.images.map((item,index)=><div key={item.id} className={'provenance-file '+(activeImage===index?'active':'')}>
          <button disabled={busy||!!working} onClick={()=>setActiveImage(index)} aria-pressed={activeImage===index}>
            {item.media_type!=='image'?<FileImage size={30}/>:<img src={urlFor(item)} alt="" loading="lazy"/>}
            <span><strong>{item.id} · {item.filename}</strong><small>{(item.size_bytes/1024/1024).toFixed(2)} {translate("MiB ·")} {item.format}</small></span>
          </button>
        </div>)}
      </section>
      <div className="provenance-report-meta"><span>{report.case.id} · {report.images.length} {translate("files ·")} {report.compared_pairs} {translate(report.pair_selection?"pairs hash/metadata checked ·":"pairs compared ·")} {report.relationships.length} {translate("connections")}</span>
        <time dateTime={report.analyzed_at}>{formatDate(report.analyzed_at)}</time></div>
      {report.pair_selection && <section className="panel" aria-label="Pair selection coverage">
        <h2>Comparison coverage · {report.pair_selection.strategy==='cp_sat'?'CP-SAT':'All eligible pairs'}</h2>
        <p><strong>{report.pair_selection.selected_visual_pairs} / {report.pair_selection.eligible_visual_pairs}</strong> eligible file pairs selected for visual verification · {report.pair_selection.cheap_checked_pairs} pairs checked for exact copies and metadata.</p>
        <details><summary>Planner details</summary><p>{report.pair_selection.solver_status} · {report.pair_selection.planning_runtime_ms.toFixed(1)} ms planning time</p><p>{report.pair_selection.limitation}</p></details>
        <details><summary>Unexamined visual pairs ({report.pair_selection.unexamined_pairs.length})</summary>
          {report.pair_selection.unexamined_pairs.length ? <ul>{report.pair_selection.unexamined_pairs.map(pair=><li key={pair.left_id+'-'+pair.right_id}>{report.images.find(item=>item.id===pair.left_id)?.filename??pair.left_id} ↔ {report.images.find(item=>item.id===pair.right_id)?.filename??pair.right_id}: not examined</li>)}</ul>:<p>No eligible visual pairs were omitted.</p>}
        </details>
        {report.pair_selection.unsupported_visual_pairs.length>0 && <p>{report.pair_selection.unsupported_visual_pairs.length} pairs have no supported visual comparison (for example audio or mixed media).</p>}
      </section>}
      {!report.visual_matching_available&&<p role="status" className="notice">{translate("Visual matching is unavailable on this backend. This report includes file hashes and metadata.")}</p>}
      <section className="panel provenance-integrity">
        <div><strong>{translate("Preserved originals and integrity anchor")}</strong><p>{report.integrity.storage}</p>
          <p className="mono provenance-hash">{translate("Report SHA-256 ·")} {report.report_sha256}</p>
          <details><summary>{translate("Verify against an externally retained anchor")}</summary>
            <label className="provenance-field">{translate("Log anchor copied from an exported report")}
              <input value={retainedAnchor} maxLength={64} onChange={event=>setRetainedAnchor(event.target.value)} placeholder={translate("Optional SHA-256 anchor")}/>
            </label>
            <p>{translate("Without a supplied anchor, verification uses the anchor in this saved analysis.")}</p>
          </details></div>
        <div className="provenance-actions"><button className="button secondary" disabled={busy||!!working} onClick={verify}>{translate("Verify preserved originals and log")}</button>
          <button className="button secondary" disabled={busy||!!working} onClick={inspectAudit}>{translate("Provenance activity")}</button></div>
      </section>
      {report.exact_duplicate_groups.length>0&&<p className="notice">{translate("Exact duplicate groups ·")} {report.exact_duplicate_groups.map(group=>group.join(' = ')).join(' / ')}</p>}
      {verification&&<section className="panel provenance-verification" role="status">
        <h2>{translate("Verification result")}</h2>
        {verification.supplied_file?<p>{verification.filename} · {verification.supplied_file.matches?'SHA-256 matches the recorded original':'SHA-256 differs from the recorded original'}</p>:<>
          <p>{translate("Preserved originals ·")} {verification.all_originals_match?'all hashes match':'verification failure'}</p>
          <p>{translate("Provenance chain ·")} {verification.chain_valid&&verification.anchor_matches?'consistent with the retained report anchor':'verification failure'}</p></>}
      </section>}
      {audit&&<section className="panel provenance-audit"><h2>{translate("Provenance activity")}</h2>
        <p>{audit.scope}</p><p>{audit.limitations}</p>
        {audit.entries.map((entry:any)=><details key={entry.sequence}><summary>{entry.sequence} · {entry.action} · {entry.actor} · {formatDate(entry.timestamp)}</summary>
          <pre>{JSON.stringify(entry,null,2)}</pre></details>)}
      </section>}
      <section className="panel provenance-area-picker" aria-label="Compare matched files">
        <h2>Compare files side by side</h2>
        {report.relationships.length ? <label>Connection <select value={selected ?? ''}
          onChange={event=>event.target.value ? selectPair(event.target.value) : setSelected(null)}>
          <option value="">Select a connection</option>
          {report.relationships.map(edge=><option key={edge.id} value={edge.id}>
            {report.images.find(file=>file.id===edge.left_id)?.filename} ↔ {report.images.find(file=>file.id===edge.right_id)?.filename} · {titleFor(edge)}
          </option>)}
        </select></label> : <p>No supported connections found.</p>}
      </section>
      {pair&&left&&right&&<section ref={citedComparison} id="provenance-comparison" className="panel provenance-comparison">
        <div className="provenance-section-heading"><h2>{titleFor(pair)}</h2>
          {pair.support&&!frameTimes&&<label><input type="checkbox" checked={showRegions} onChange={event=>setShowRegions(event.target.checked)}/>{translate("Show matching points and regions")}</label>}
        </div>
        <p>{pair.explanation}</p>
        {pair.metadata_fields&&<div className="provenance-link-evidence">{Object.entries(pair.metadata_fields).map(([key,value])=><p key={key}>{key} {translate("agrees ·")} {value}</p>)}</div>}
        {pair.manifest_labels&&<div className="provenance-link-evidence">{pair.manifest_labels.map(value=><p className="mono" key={value}>{value}</p>)}</div>}
        {pair.kind==='exact_copy'&&<div className="provenance-link-evidence"><p className="mono">{translate("Both SHA-256 values ·")} {left.sha256}</p></div>}
        {frameTimes&&<p>{translate("Strongest sampled match at")} {(frameTimes[0]/1000).toFixed(2)} {translate("s and")} {(frameTimes[1]/1000).toFixed(2)} {translate("s.")}
          {' '}{pair.support?.sample_pair_count} {translate("sampled frame pairs compared.")}</p>}
        {pair.support&&!frameTimes&&<div className="provenance-link-evidence">
          <p>{pair.support.candidate_search} {translate("· dHash distance")} {pair.support.hash_distance}</p>
          <button className="button secondary" onClick={()=>setShowDifference(value=>!value)}>{showDifference?'Hide':'Show'} {translate("aligned difference overlay")}</button>
          {showDifference&&<figure><img className="provenance-difference" src={provenanceEndpoint(baseUrl,'/reports/'+report.analysis_id+'/relationships/'+pair.id+'/difference')} alt={translate("Aligned image with residual pixel differences highlighted in red")}/>
            <figcaption>{translate("Red marks residual differences in the aligned overlap. Compression, lighting and alignment can also produce these differences.")}</figcaption></figure>}
        </div>}
        <div className="provenance-compare-images">
          <figure><ImagePreview src={urlFor(left)} name={left.filename} mediaType={left.media_type} timestamp={frameTimes?.[0]} area={left.comparison_area} region={showRegions?pair.support?.left_region:undefined} points={showRegions?pair.support?.point_pairs?.map(point=>[point[0],point[1]]):undefined}/>
            <figcaption>{left.id} · {left.filename}</figcaption></figure>
          <figure><ImagePreview src={urlFor(right)} name={right.filename} mediaType={right.media_type} timestamp={frameTimes?.[1]} area={right.comparison_area} region={showRegions?pair.support?.right_region:undefined} points={showRegions?pair.support?.point_pairs?.map(point=>[point[2],point[3]]):undefined}/>
            <figcaption>{right.id} · {right.filename}</figcaption></figure>
        </div>
        {pair.support&&!frameTimes&&<p className="muted small">{pair.support.point_pairs?'Teal dots show sampled points accepted by RANSAC. ':''}{translate("Dashed boxes mark selected photo areas. They show shared regions and do not locate an edit. Geometric agreement")} {(pair.support.geometric_inlier_ratio*100).toFixed(0)}{translate("% of candidate feature matches.")}</p>}
      </section>}
      <div className="provenance-workspace">
        <details className="panel provenance-relations">
          <summary>Relationship map</summary>
          <div className="provenance-section-heading">
            <div><h2>Evidence Relationship Map</h2><p className="muted small">Select a link to see its evidence.</p></div>
            <span className="badge">{report.images.length} files · {visibleRelationships.length} links shown</span>
          </div>
          <div className="provenance-map-tools" role="group" aria-label="Filter connections">
            {[['all','All links'],...Object.entries(edgeStyles).map(([id,style])=>[id,style.label])].map(([kind,label])=>
              <button type="button" className="button secondary" key={kind} aria-pressed={filter===kind}
                onClick={()=>{setFilter(kind);setSelected(null);setShowDifference(false)}}>
                {kind!=='all'&&<i style={{borderColor:edgeStyles[kind].color,borderTopStyle:edgeStyles[kind].dash?'dashed':'solid'}}/>}{label}
              </button>)}
          </div>
          <RelationshipGraph key={report.analysis_id} report={report} onSelect={selectPair} selected={selected} onFile={index=>{setActiveImage(index);setSelected(null);setShowDifference(false)}} filter={filter} activeImage={activeImage} imageUrl={urlFor}/>
          <p className="provenance-map-help">Creation order remains unverified.</p>
          <div className="provenance-connections" aria-label="Connections">
            {visibleRelationships.length===0?<p>No supported connections of this type found. This does not prove files are unrelated.</p>:visibleRelationships.map(edge=>
              <button key={edge.id} className={selected===edge.id?'active':''} onClick={()=>selectPair(edge.id)} aria-pressed={selected===edge.id}>
                {edge.kind==='exact_copy'?<Hash size={17}/>:<GitBranch size={17}/>}
                <span><strong>{titleFor(edge)} · {linkProof(edge)}</strong><small>{report.images.find(item=>item.id===edge.left_id)?.filename} ↔ {report.images.find(item=>item.id===edge.right_id)?.filename}</small></span>
              </button>)}
          </div>
        </details>
        <div className="provenance-map-sidebar">
        {pair&&left&&right&&<section className="panel provenance-map-selection" style={{borderInlineStartColor:edgeStyles[pair.kind].color}} aria-label="Selected connection evidence">
          <span className="muted small">SELECTED CONNECTION</span>
          <h2>{titleFor(pair)}</h2>
          <p className="provenance-map-proof" style={{color:edgeStyles[pair.kind].color}}>{linkProof(pair)}</p>
          <div className="provenance-map-pair">{[left,right].map(item=><div key={item.id}>
            {item.media_type==='image'&&<img alt="" src={urlFor(item)}/>}
            <strong title={item.filename}>{item.filename}</strong>
          </div>)}</div>
          <p>{pair.explanation}</p>
          <button type="button" className="button primary" onClick={()=>document.getElementById('provenance-comparison')?.scrollIntoView({block:'start'})}>View supporting evidence</button>
        </section>}
        <aside className="panel provenance-source">
          <div className="provenance-section-heading"><h2>{translate("Recorded source")}</h2><FileImage size={17}/></div>
          {source&&<>
            <label className="provenance-field">{translate("Examine file")}<select disabled={busy||!!working} value={activeImage} onChange={event=>setActiveImage(+event.target.value)}>
              {report.images.map((item,index)=><option value={index} key={item.id}>{item.id} · {item.filename}</option>)}
            </select></label>
            {source.case_intake&&<div className="provenance-link-evidence">
              <strong>{translate("Case intake")}</strong>
              <p>{source.case_intake.registered_at} · {source.case_intake.registered_by} {translate("(self-declared)")}</p>
              {source.case_intake.receipt?.supplied_by&&<p>{translate("Supplied by (reported) ·")} {source.case_intake.receipt.supplied_by}</p>}
              {source.case_intake.receipt?.collection_reference&&<p>{translate("Collection reference (reported) ·")} {source.case_intake.receipt.collection_reference}</p>}
              {source.case_intake.receipt?.note&&<p>{source.case_intake.receipt.note}</p>}
            </div>}
            {source.video_coverage&&<p>{translate("Examined")} {source.video_coverage.examined_timestamps_ms.length} {translate("of")} {source.video_coverage.source_frame_timestamps} {translate("recorded frame timestamps.")}
              {' '}{translate("Sample times:")} {source.video_coverage.examined_timestamps_ms.map(time=>(time/1000).toFixed(2)+' s').join(', ')}.</p>}
            <ImagePreview src={urlFor(source)} name={source.filename} mediaType={source.media_type} area={source.comparison_area}/>
            <p>{source.source_observation}</p>
            <p className="muted small">{source.metadata_status}</p>
            {source.metadata_flags.map(flag=><p className="notice" key={flag}>{flag}</p>)}
            <button className="button secondary" disabled={busy||!!working} onClick={()=>verifyInput.current?.click()}>{translate("Verify a local original")}</button>
            <input ref={verifyInput} type="file" hidden onChange={event=>{if(event.target.files?.[0])void verifyLocal(event.target.files[0]);event.target.value=''}}/>
            <dl><dt>{translate("File")}</dt><dd>{source.media_type==='image'?source.width+' × '+source.height+' · ':''}{source.format}</dd>
              {Object.entries(source.metadata).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}
              <dt>SHA-256</dt><dd className="mono provenance-hash">{source.sha256}</dd>
            </dl>
            <div className="provenance-credentials"><strong>{translate("Content Credentials")}</strong><p>{source.content_credentials.observation}</p>
              <p>{translate("Signature ·")} {source.content_credentials.signature||'unknown'}</p>
              <p>{translate("File binding ·")} {source.content_credentials.content_binding||'unknown'}</p>
              <p>{translate("Signer trust ·")} {source.content_credentials.signer_trust||'unknown'}</p>
              {source.content_credentials.trust_policy&&<p>{source.content_credentials.trust_policy}</p>}
              {(['signer','tools','actions','validation_status'] as const).map(key=>source.content_credentials[key]&&<details key={key}><summary>{key.replace('_',' ')}</summary><pre>{JSON.stringify(source.content_credentials[key],null,2)}</pre></details>)}
            </div>
            <section className="provenance-signals"><h3>{translate("Supporting detector signals")}</h3>
              <button className="button secondary" disabled={busy||!!working||source.media_type==='video'} onClick={runSignals}>{translate("Run supporting detectors")}</button>
              {source.detector_signals.length===0&&<p>{translate("No detector signals requested for this file.")}</p>}
              {source.detector_signals.map((signal:any)=><details key={signal.finding_id}><summary>{signal.method} {translate("· score")} {signal.score?.value?.toFixed(3)??'unavailable'}</summary>
                <p>{signal.method_version}</p><p>{signal.observation}</p>
                {signal.limitations.map((limit:string)=><p key={limit}>{limit}</p>)}</details>)}
            </section>
          </>}
        </aside>
        </div>
      </div>

      <section className="panel provenance-review">
        <h2>{translate("Reviewer interpretations")}</h2>
        <p>{translate("Record your reasoning separately from machine observations. Notes are attributed to a self-declared reviewer and retained in immutable analysis revisions.")}</p>
        <label>{translate("Review scope")}<select value={reviewScope} onChange={event=>setReviewScope(event.target.value)} disabled={busy||!!working}>
          <option value="">{translate("Whole analysis")}</option>{report.images.map(item=><option key={item.id} value={item.id}>{item.id} · {item.filename}</option>)}
          {report.relationships.map(edge=><option key={edge.id} value={edge.id}>{edge.left_id} ↔ {edge.right_id} · {titleFor(edge)}</option>)}
        </select></label>
        <label>{translate("Interpretation")}<textarea value={reviewText} maxLength={4000} rows={4} disabled={busy||!!working} onChange={event=>setReviewText(event.target.value)} placeholder={translate("Describe the evidence, your interpretation and any uncertainty.")}/></label>
        <button className="button secondary" disabled={!!working||!reviewText.trim()||!analyst.trim()} onClick={saveReview}>{translate("Save review as new revision")}</button>
        {report.review_notes.map((note,index)=><article key={index}><strong>{note.author} · {formatDate(note.timestamp)}</strong><p>{translate("Scope:")} {note.scope_id||translate('Whole analysis')} {translate("· Analysis:")} {note.analysis_id}</p><p className="provenance-note-text">{note.text}</p></article>)}
      </section>
      {unconnected.length>0&&<section className="panel provenance-unconnected"><h2>{translate("Files without a supported visual link")}</h2>
        <p>{unconnected.map(item=>item.id+' · '+item.filename).join('; ')}</p><p>{translate("There was insufficient visual evidence to establish a link for these files. Heavy edits, low texture or different content can explain this; it is not a verdict of authenticity or unrelatedness. Audio similarity is not evaluated.")}</p>
      </section>}
      {unmatchedPairs.length>0&&<details className="panel provenance-unconnected">
        <summary>{translate("Insufficient visual evidence for")} {unmatchedPairs.length} {translate("image")} {unmatchedPairs.length===1?'pair':'pairs'}</summary>
        <ul>{unmatchedPairs.map(({left,right})=><li key={left.id+'/'+right.id}>{left.filename} ↔ {right.filename}</li>)}</ul>
      </details>}
      <section className="panel provenance-report-scope"><h2>{translate("Report scope")}</h2>
        <p className="mono">{report.analysis_id}</p>
        <p>{report.integrity.limitations}</p>
        <ul>{report.limitations.map(limit=><li key={limit}>{limit}</li>)}</ul>
        <details><summary>{translate("Methods and versions")}</summary><pre>{JSON.stringify(report.methods,null,2)}</pre></details>
      </section>
    </>}
  </div>;
}
