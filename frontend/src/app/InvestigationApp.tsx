import {CaseAutomationProgress} from '../components/CaseAutomationProgress';
import {ReportsWorkspace} from '../reports/ReportsWorkspace';
import {translate,type MessageKey,type MessageParams} from '../i18n';
import {BrandMark} from '../components/BrandMark';
import {latestCaseProvenance,type ProvenanceReport} from '../data/provenance';
import {ProvenanceLab} from '../pages/ProvenanceLab';
import {scanEvidence, type DetectionScan} from '../data/detectionScan';
import {ReferenceComparison, VisualInspection} from '../components/viewer/VisualInspection';
import {DetectionWorkspace} from '../components/findings/DetectionWorkspace';
import {SERVER_INTAKE, listEvidence, preserveEvidence, sampleFinding, verifyEvidence} from '../evidenceApi';
import {makeReportSnapshot, type ReportSnapshot} from '../reportSnapshot';
import React,{useState,useEffect,useRef,useReducer} from 'react';
import {Activity,ArrowDownToLine,ArrowLeft,ArrowRight,ArrowUpRight,AudioLines,Bell,BookOpen,Check,CheckCheck,ChevronDown,ChevronLeft,ChevronRight,ChevronsUpDown,ChevronUp, CircleHelp,Clock,Copy,Database,Download,Ellipsis,File,FileCheck,FileImage,FileJson,FileText,Film,FlaskConical,Folder,FolderOpen,GitBranch,Globe,Hash,History,Image as ImageIcon,Info,Layers,Link, ListFilter,Loader2,Lock,Maximize2,Mic,Minus,Monitor, Moon,MoreHorizontal,Pause,Play,Plus,Search,Settings2,Shield,ShieldCheck,SlidersHorizontal,Square,Sun,Target,TriangleAlert,Upload,X,XCircle,ZoomIn,ZoomOut} from 'lucide-react';
import {channels,classification,tone,download,Finding,Evidence,CaseRecord,Note,Channel,ApiEvidence} from '../model';
import Landing from '../Landing';
import {AppShell} from './AppShell';
import {AppPage,navigate,parseHash,routeFor} from './routing';
import {I18nProvider,useI18n} from '../i18n';
import {EvidenceTable} from '../components/EvidenceTable';
import {ProcessingSummary} from '../components/ProcessingSummary';
import {CaseList} from '../pages/CaseList';
import {CaseNotFound,RouteNotFound} from '../pages/RouteStates';
import {evidenceForCase} from '../data/caseView';
import {apiBaseUrl,caseSource,CaseSourceError,caseOriginalUrl,uploadCaseOriginal} from '../data/caseSource';
import {selectProcessingSummary} from '../selectors/processing';
import {loadDevelopmentFixtures} from '../data/fixtureSource';
import type {RunRecord} from '../runs/types';
import {newestFirst} from '../runs/presentation';
import {createRetryRun,createRunId} from '../runs/retry';
import {MemoryRunSource} from '../data/runSource';
import {ApiRunSource,RunApiError} from '../data/apiRunSource';
import {RunHistoryPanel} from '../components/runs/RunHistoryPanel';
import {RunStatusBadge} from '../components/runs/RunStatusBadge';
import type {SimulationOutcome} from '../data/fixtureSimulation';
import {EvidenceViewer} from '../components/viewer/EvidenceViewer';
import {emptySelection,selectionReducer} from '../viewer/selection';
import {findingInterval,findingPositionMs,overlappingFindingIds} from '../viewer/markers';
import {serializeViewerUrlState} from '../viewer/urlState';
import {FindingsPanel} from '../components/findings/FindingsPanel';
import {TechnicalDetailsDrawer} from '../components/findings/TechnicalDetailsDrawer';
import {migrateLegacyNotes} from '../findings/review';
import {createReviewApi} from '../data/reviewApi';
import {Evaluation} from '../pages/Evaluation';
import {MediaAnalysis} from '../pages/MediaAnalysis';
import {ReviewReport} from '../pages/ReviewReport';
import {CaseBriefingPanel} from '../components/CaseBriefingPanel';
import {CaseAuditView,RecentActivity} from '../components/CaseActivity';
import {PersonalApp} from '../personal/PersonalApp';
import '../style.css';
const FIXTURE=import.meta.env.VITE_DEV_FIXTURE==='true';
const API=caseSource.mode==='api';
const iconFor=(type:string)=>type==='video'?Film:type==='audio'?AudioLines:FileImage;
const fmt=(n:number)=>`${Math.floor(n/60).toString().padStart(2,'0')}:${Math.floor(n%60).toString().padStart(2,'0')}`;
type UiMessage={key:MessageKey;params?:MessageParams}|{verbatim:string};
const messageText=(message:UiMessage,language?:'en'|'hi')=>'verbatim' in message?message.verbatim:translate(message.key,message.params,language);
const evidenceFromApi=(item:ApiEvidence):Evidence=>({id:item.evidence_id,caseId:item.case_id,name:item.filename,type:item.media_type,role:item.role,size:`${(item.size_bytes/1024/1024).toFixed(2)} MB`,duration:'—',received:item.registered_at,registeredBy:item.registered_by,receipt:item.receipt??undefined,hash:item.sha256,fixture:false,preserved:item.preserved,source:item.preserved?caseOriginalUrl(item.case_id,item.evidence_id,item.media_type==='image'):undefined,status:item.preserved?'Original preserved':'Inventory only',dimensions:item.preserved?'Server-verified SHA-256':'A hash-matched analysis copy is retained only after a run'});
function Badge({children,t='neutral'}:{children:React.ReactNode;t?:string}){return <span className={`badge ${t}`}><span className="badge-dot"/>{children}</span>}
function FindingBadge({f}:{f:Finding}){return <Badge t={tone(f)}>{classification(f)}</Badge>}
function OfficeStill({small=false}:{small?:boolean}){return <svg className={'office-still '+(small?'small':'')} viewBox="0 0 900 500" role="img" aria-label={translate("Illustrative office scene for fixture evidence")}><defs><linearGradient id="wall" x2="0" y2="1"><stop stopColor="#525d61"/><stop offset="1" stopColor="#303b40"/></linearGradient><linearGradient id="window" x2="0" y2="1"><stop stopColor="#9da9a7"/><stop offset="1" stopColor="#677d7d"/></linearGradient><filter id="grain"><feTurbulence baseFrequency=".6" numOctaves="3" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope=".08"/></feComponentTransfer></filter></defs><rect width="900" height="500" fill="url(#wall)"/><path d="M0 0h250v365L0 480Z" fill="#263337"/><rect x="290" y="35" width="485" height="270" fill="url(#window)"/><g fill="#495d61" opacity=".55"><rect x="320" y="170" width="45" height="135"/><rect x="380" y="125" width="70" height="180"/><rect x="480" y="190" width="55" height="115"/><rect x="559" y="100" width="60" height="205"/><rect x="643" y="150" width="100" height="155"/></g><g stroke="#28383c" strokeWidth="10"><path d="M295 35v270m160-270v270m160-270v270M290 165h485"/></g><path d="m0 500 260-145h640v145Z" fill="#202d32"/><path d="m180 392 420-72 245 105-476 75Z" fill="#64706c"/><path d="m180 392 189 108v-17L180 378Z" fill="#4c5755"/><path d="m180 393 420-72 245 105-476 57Z" fill="#73807a"/><path d="m266 440 4 60m486-62 3 62" stroke="#253339" strokeWidth="14"/><rect x="466" y="251" width="112" height="86" rx="4" fill="#14242c" transform="rotate(-4 466 251)"/><rect x="473" y="258" width="98" height="68" rx="2" fill="#304c56" transform="rotate(-4 473 258)"/><path d="m523 333 2 27m-25 5 50-8" stroke="#1d3036" strokeWidth="7"/><path d="m421 371 70-10 39 15-74 11Z" fill="#a5ada4"/><ellipse cx="669" cy="370" rx="16" ry="7" fill="#c0c4b4"/><path d="M653 340h29l-3 28h-22Z" fill="#b4bbaa"/><g fill="#263b36"><ellipse cx="818" cy="245" rx="22" ry="48" transform="rotate(-30 818 245)"/><ellipse cx="850" cy="223" rx="18" ry="51" transform="rotate(14 850 223)"/><ellipse cx="877" cy="263" rx="17" ry="40" transform="rotate(42 877 263)"/></g><path d="M830 306h46l-8 67h-30Z" fill="#4d5d57"/><path d="M121 276q80-37 83 36v83l-99 35v-97Z" fill="#1c2c31"/><path d="m148 417 1 66m-32 6 66-18" stroke="#0f2027" strokeWidth="9"/><rect width="900" height="500" filter="url(#grain)" opacity=".7"/><path d="M0 0h900v500H0Z" fill="#0b1a24" opacity=".14"/></svg>}
function InvestigationApp({initialModal=null,onHome}:{initialModal?:string|null;onHome:()=>void}){
 const saved=<T,>(key:string,fallback:T):T=>{try{return JSON.parse(localStorage.getItem(key)||'null')??fallback}catch{return fallback}};
 const sessionSaved=<T,>(key:string,fallback:T):T=>{try{return JSON.parse(sessionStorage.getItem(key)||'null')??fallback}catch{return fallback}};
 const [cases,setCases]=useState<CaseRecord[]>(()=>API?[]:saved('pratyaksh-cases',[]));
 const [notes,setNotes]=useState<Note[]>(()=>migrateLegacyNotes(saved<unknown>('pratyaksh-notes',[])));
 const initialRoute=parseHash(window.location.hash);const [page,setPageState]=useState<AppPage>(initialRoute.page);const [routePath,setRoutePath]=useState(initialRoute.path);const [caseId,setCaseIdState]=useState(initialRoute.caseId||cases[0]?.id||'');const caseIdRef=useRef(caseId);const setCaseId=(value:string)=>{caseIdRef.current=value;setCaseIdState(value)};const [selected,setSelected]=useState(initialRoute.evidenceId||'EVID-001');const [items,setItems]=useState<Evidence[]>([]);const [fixtureFindings,setFindings]=useState<Finding[]>([]);const[runs,setRuns]=useState<RunRecord[]>([]);const[findingRunId,setFindingRunId]=useState<string|null>(initialRoute.runId||null);const[runAnnouncement,setRunAnnouncement]=useState<UiMessage|null>(null);const[viewerSelection,dispatchViewer]=useReducer(selectionReducer,{...emptySelection,findingId:initialRoute.findingId||null,positionMs:initialRoute.positionMs||0,interval:initialRoute.startMs!=null&&initialRoute.endMs!=null?{startMs:initialRoute.startMs,endMs:initialRoute.endMs}:null});const objectUrls=useRef(new Set<string>());
 const [query,setQuery]=useState('');const [filter,setFilter]=useState('All evidence');const [modal,setModal]=useState<string|null>(initialModal);const [toast,setToast]=useState<UiMessage|null>(null);const [tab,setTab]=useState('Viewer');const [light,setLight]=useState(true);const [jobsOpen,setJobsOpen]=useState(true);const [technical,setTechnical]=useState<Finding|null>(null);const [selectedFinding,setSelectedFinding]=useState<Finding|null>(null);const [time,setTime]=useState(8);const [zoom,setZoom]=useState(100);const [playing,setPlaying]=useState(false);const [overlay,setOverlay]=useState(false);const [reportSnapshots,setReportSnapshots]=useState<Record<string,ReportSnapshot[]>>(()=>saved('pratyaksh-report-snapshots',{}));
 const [snapshotRevision,setSnapshotRevision]=useState<number|null>(null);
 const snapshots=reportSnapshots[caseId]||[];
 const selectedSnapshot=snapshots.find(record=>record.revision===snapshotRevision);
 const reportVersion=snapshots.length;
 const [sampleIds,setSampleIds]=useState<string[]>(()=>saved('pratyaksh-sample-ids',[]));
 const [verifying,setVerifying]=useState(false);
 const [reportSections,setReportSections]=useState<string[]>(()=>sessionSaved('pratyaksh-report-sections',['Evidence inventory','Methods and scope','Forensic findings','Limitations','Analyst notes']));const [preparer,setPreparer]=useState('Demo analyst');const [menu,setMenu]=useState(false);const [activeChannel,setActiveChannel]=useState<Channel|null>(null);const [audit,setAudit]=useState<UiMessage[]>([]);
 const [casesLoading,setCasesLoading]=useState(API);const [casesError,setCasesError]=useState('');const [evidenceLoading,setEvidenceLoading]=useState(false);const [evidenceError,setEvidenceError]=useState('');const [caseSaving,setCaseSaving]=useState(false);const [backendHealth,setBackendHealth]=useState(API?'Checking backend…':'Local prototype · backend not configured');
 const [scans,setScans]=useState<Record<string,DetectionScan>>({});
 const [caseProvenance,setCaseProvenance]=useState<ProvenanceReport|null>(null);
 const [provenanceLoading,setProvenanceLoading]=useState(false);
 const [provenanceError,setProvenanceError]=useState('');
 const [scanning,setScanning]=useState(false);
 const [scanErrors,setScanErrors]=useState<Record<string,string>>({});
 const [simulationOutcome,setSimulationOutcome]=useState<SimulationOutcome>('completed');
 const [preservedItems,setPreservedItems]=useState<Evidence[]>([]);
 const runSubmissions=useRef(new Set<string>());
 const activeCase=cases.find(c=>c.id===caseId);const evidence=[
  ...(API?items.filter(item=>item.caseId===caseId):evidenceForCase(items,caseId)),
  ...preservedItems.filter(item=>item.caseId===caseId),
 ];
 const evidenceIds=new Set(evidence.map(item=>item.id));
 const [loadedFindingCase,setLoadedFindingCase]=useState('');
 const caseRuns=runs.filter(run=>!API||run.case_id===caseId);
 const findingsById=new Map<string,Finding>();
 for(const finding of [
  ...fixtureFindings.filter(finding=>(!API||loadedFindingCase===caseId)&&evidenceIds.has(finding.evidence_id)),
  ...Object.values(scans).flatMap(scan=>evidenceIds.has(scan.evidence_id)?scan.findings:[]),
  ...caseRuns.flatMap(run=>evidenceIds.has(run.evidence_id)?run.findings:[]),
  ...evidence.filter(item=>sampleIds.includes(item.id)).map(item=>sampleFinding(item.id)),
 ])findingsById.set(finding.finding_id,finding);
 const findings=[...findingsById.values()];const current=evidence.find(e=>e.id===selected)||evidence[0];const caseNotes=notes.filter(n=>findings.some(f=>f.finding_id===n.findingId));const currentRuns=current?newestFirst(caseRuns.filter(run=>run.evidence_id===current.id)):[];const currentRun=currentRuns[0];const activeFindingRun=findingRunId&&currentRuns.some(run=>run.run_id===findingRunId)?findingRunId:currentRuns.find(run=>run.findings.length)?.run_id;const currentFindings=findings.filter(f=>f.evidence_id===current?.id&&(!activeFindingRun||f.run_id===activeFindingRun||currentRuns.find(run=>run.run_id===activeFindingRun)?.findings.some(item=>item.finding_id===f.finding_id)));const overlapIds=overlappingFindingIds(currentFindings,viewerSelection.interval,viewerSelection.positionMs);const processing=selectProcessingSummary(evidence,findings,caseRuns);const fileRef=useRef<HTMLInputElement>(null);const [uploadFiles,setUploadFiles]=useState<File[]>([]);const [receipt,setReceipt]=useState('');const [suppliedBy,setSuppliedBy]=useState('');const [collectionReference,setCollectionReference]=useState('');const [uploading,setUploading]=useState(false);
 useEffect(()=>{if(!modal&&!technical)return;const prior=document.activeElement as HTMLElement;const dialog=document.querySelector<HTMLElement>(modal?'.modal':'.technical-drawer');const nodes=()=>Array.from(dialog?.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([hidden]),textarea,select,[tabindex="0"]')||[]);nodes()[0]?.focus();const trap=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.preventDefault();setModal(null);setTechnical(null);return}if(e.key!=='Tab')return;const list=nodes(),first=list[0],last=list[list.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}};document.addEventListener('keydown',trap);return()=>{document.removeEventListener('keydown',trap);prior?.focus()}},[modal,technical]);
 const notify=(message:UiMessage|string)=>{setToast(typeof message==='string'?{verbatim:message}:message);setTimeout(()=>setToast(null),4500)};
 useEffect(()=>{let active=true;loadDevelopmentFixtures().then(fixtures=>{if(!active||!fixtures)return;setCases(current=>current.length?current:fixtures.cases);setItems(current=>[...current.filter(item=>!item.fixture),...fixtures.evidence]);setFindings(fixtures.findings);setRuns(fixtures.runs);if(!caseIdRef.current&&fixtures.cases[0]&&['Overview','Evidence','Workbench'].includes(parseHash(window.location.hash).page)){setCaseId(fixtures.cases[0].id);navigate(routeFor('Overview',fixtures.cases[0].id))}}).catch(error=>{if(active)setCasesError(error instanceof Error?`Fixture validation failed: ${error.message}`:'Fixture validation failed')});return()=>{active=false}},[]);
 useEffect(()=>{
  if(page!=='Workbench'||!caseId||!current||current.id!==selected||evidenceLoading)return;
  const expectedHash=window.location.hash;
  const timer=setTimeout(()=>{
   if(window.location.hash!==expectedHash)return;
   const base=routeFor('Workbench',caseId,current.id,tab,{findingId:viewerSelection.findingId,runId:findingRunId||activeFindingRun});
   const query=serializeViewerUrlState(viewerSelection);
   history.replaceState(null,'',`#${base}${query?(base.includes('?')?'&':'?')+query:''}`);
  },180);
  return()=>clearTimeout(timer);
 },[page,caseId,selected,current?.id,tab,findingRunId,activeFindingRun,evidenceLoading,viewerSelection.findingId,viewerSelection.positionMs,viewerSelection.interval?.startMs,viewerSelection.interval?.endMs]);
 useEffect(()=>()=>{objectUrls.current.forEach(url=>URL.revokeObjectURL(url));objectUrls.current.clear()},[]);
 useEffect(()=>{const live=new Set(items.flatMap(item=>item.source?[item.source]:[]));objectUrls.current.forEach(url=>{if(!live.has(url)){URL.revokeObjectURL(url);objectUrls.current.delete(url)}})},[items]);
 useEffect(()=>{if(!API)localStorage.setItem('pratyaksh-cases',JSON.stringify(cases))},[cases]);useEffect(()=>{if(!API)try{localStorage.setItem('pratyaksh-notes',JSON.stringify(notes))}catch{}},[notes]);
 useEffect(()=>{try{sessionStorage.setItem('pratyaksh-report-sections',JSON.stringify(reportSections))}catch{}},[reportSections]);
 useEffect(()=>{let active=true;caseSource.health().then(result=>{if(active)setBackendHealth(result.message)}).catch(error=>{if(active)setBackendHealth(error instanceof Error?error.message:'Backend unavailable')});if(API){setCasesLoading(true);caseSource.listCases().then(records=>{if(!active)return;setCases(current=>[...records.filter(record=>!current.some(item=>item.id===record.id)),...current]);setCasesError('');if(!caseIdRef.current&&records[0]&&['Overview','Evidence','Workbench'].includes(parseHash(window.location.hash).page))navigate(routeFor('Overview',records[0].id))}).catch(error=>{if(active)setCasesError(error instanceof Error?error.message:'Cases could not be loaded')}).finally(()=>{if(active)setCasesLoading(false)})}return()=>{active=false}},[]);
 const [runStatusErrors,setRunStatusErrors]=useState<Record<string,string>>({});
 const runStatusError=runStatusErrors[caseId];
 const [caseReload,setCaseReload]=useState(0);
 const [resolvedCaseId,setResolvedCaseId]=useState('');
 const [caseLookupError,setCaseLookupError]=useState('');
 const runSubscriptions=useRef(new Map<string,()=>void>());
 function watchRun(source:ApiRunSource,run:RunRecord,onStop?:()=>void){
  runSubscriptions.current.get(run.run_id)?.();
  const stop=()=>{
   runSubscriptions.current.get(run.run_id)?.();
   runSubscriptions.current.delete(run.run_id);
   onStop?.();
  };
  runSubscriptions.current.set(run.run_id,source.subscribe(run.run_id,updated=>{
   setRuns(current=>[...current.filter(item=>item.run_id!==updated.run_id),updated]);
    if(updated.execution_status!=='queued'&&updated.execution_status!=='running'){notify({key:'session.analysisFinished'});stop()}
  },error=>{
   setRunStatusErrors(current=>({...current,[run.case_id||caseId]:`Status unavailable for ${run.run_id}: ${error.message}`}));
   stop();
  }));
 }
 useEffect(()=>()=>{runSubscriptions.current.forEach(cancel=>cancel());runSubscriptions.current.clear()},[]);
 useEffect(()=>{
  if(!API||page!=='Workbench'||!caseId||!selected||!findingRunId)return;
  const controller=new AbortController();
  const source=new ApiRunSource(apiBaseUrl);
  void source.getRun(findingRunId,controller.signal).then(run=>{
   if(controller.signal.aborted||run.case_id!==caseId||run.evidence_id!==selected)return;
   if(runSubscriptions.current.has(run.run_id))return;
   setRuns(current=>[...current.filter(item=>item.run_id!==run.run_id),run]);
   if(run.execution_status==='queued'||run.execution_status==='running')watchRun(source,run);
  }).catch(error=>{
   if(!controller.signal.aborted&&!(error instanceof RunApiError&&error.status===404)){
    setRunStatusErrors(current=>({...current,[caseId]:'The linked run could not be loaded.'}));
   }
  });
  return()=>controller.abort();
 },[page,caseId,selected,findingRunId]);
 useEffect(()=>{
  if(!API||!caseId)return;
  let active=true;
  setResolvedCaseId('');
  setCaseLookupError('');
  caseSource.getCase(caseId).then(record=>{
   if(active)setCases(current=>[record,...current.filter(item=>item.id!==record.id)]);
  }).catch(error=>{
   if(!active)return;
   if(error instanceof CaseSourceError&&error.status===404)setCases(current=>current.filter(item=>item.id!==caseId));
   else setCaseLookupError(error instanceof Error?error.message:'Case could not be loaded.');
  }).finally(()=>{if(active)setResolvedCaseId(caseId)});
  return()=>{active=false};
 },[caseId,caseReload]);
 useEffect(()=>{
  if(!API||!caseId)return;
  const controller=new AbortController();
  const source=new ApiRunSource(apiBaseUrl);
  const active=()=>!controller.signal.aborted;
  setEvidenceLoading(true);
  setEvidenceError('');
  setRunStatusErrors(current=>({...current,[caseId]:''}));
  const inventory=caseSource.listEvidence(caseId).then(records=>{
   if(!active())return;
   setItems(current=>[...current.filter(item=>item.caseId!==caseId),...records.map(evidenceFromApi)]);
   void Promise.allSettled(records.map(item=>source.listRuns(item.evidence_id,caseId))).then(histories=>{
    if(!active())return;
    const loaded=histories.flatMap(result=>result.status==='fulfilled'?result.value:[]);
    const unwatched=loaded.filter(run=>!runSubscriptions.current.has(run.run_id));
    setRuns(current=>[...current.filter(item=>!unwatched.some(run=>run.run_id===item.run_id)),...unwatched]);
    if(histories.some(result=>result.status==='rejected'))setRunStatusErrors(current=>({...current,[caseId]:'Some run histories could not be loaded.'}));
    loaded.filter(run=>run.execution_status==='queued'||run.execution_status==='running')
      .filter(run=>!runSubscriptions.current.has(run.run_id)).forEach(run=>watchRun(source,run));
   });
  }).catch(error=>{if(active())setEvidenceError(error instanceof Error?error.message:'Evidence inventory could not be loaded')});
  const review=createReviewApi(apiBaseUrl).listFindings(caseId,controller.signal).then(findings=>{
   if(active()){setFindings(findings);setLoadedFindingCase(caseId)}
  }).catch(()=>{if(active())setRunStatusErrors(current=>({...current,[caseId]:'Saved findings could not be loaded.'}))});
  void inventory.finally(()=>{if(active())setEvidenceLoading(false)});
  void review;
  return()=>controller.abort();
 },[caseId,caseReload]);
 useEffect(()=>{
  if(!SERVER_INTAKE||!caseId)return;
  const controller=new AbortController();
  listEvidence(caseId,controller.signal).then(records=>setPreservedItems(previous=>{
   const known=new Set(previous.map(item=>item.id));
   return [...previous,...records.filter(record=>!known.has(record.id))];
  })).catch(()=>{if(!controller.signal.aborted)setEvidenceError('The local evidence intake service is unavailable.')});
  return ()=>controller.abort();
 },[caseId]);
 useEffect(()=>{
  setCaseProvenance(null);
  setProvenanceError('');
  if(!API||!caseId||!['ReviewReport','Overview','Workbench'].includes(page)){setProvenanceLoading(false);return}
  const controller=new AbortController();
  setProvenanceLoading(true);
  latestCaseProvenance(import.meta.env.VITE_D1_API_BASE_URL?.trim()||apiBaseUrl,caseId,controller.signal)
    .then(result=>{if(!controller.signal.aborted)setCaseProvenance(result)})
    .catch(error=>{if(!controller.signal.aborted)setProvenanceError(error instanceof Error?error.message:'Case provenance unavailable')})
    .finally(()=>{if(!controller.signal.aborted)setProvenanceLoading(false)});
  return ()=>controller.abort();
 },[caseId,page]);
 useEffect(()=>setSnapshotRevision(null),[caseId]);
 useEffect(()=>{document.documentElement.dataset.theme=light?'light':'dark'},[light]);
 useEffect(()=>{if(!playing)return;const t=setInterval(()=>setTime(v=>v>=32?0:v+.25),250);return ()=>clearInterval(t)},[playing]);
 useEffect(()=>{const handler=(e:KeyboardEvent)=>{if(e.key==='Escape'){setModal(null);setTechnical(null);setMenu(false)}if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();document.querySelector<HTMLInputElement>('.global-search input')?.focus()}};window.addEventListener('keydown',handler);return ()=>window.removeEventListener('keydown',handler)},[]);
 useEffect(()=>{
  const sync=()=>{
   let route=parseHash(window.location.hash);
   if(route.redirectTo){history.replaceState(null,'',`#${route.redirectTo}`);route=parseHash(`#${route.redirectTo}`)}
   setPageState(route.page);
   setRoutePath(route.path);
   if(route.caseId)setCaseId(route.caseId);
   if(route.page!=='Workbench')return;
   if(route.evidenceId)setSelected(route.evidenceId);
   setTab(route.tab?route.tab[0].toUpperCase()+route.tab.slice(1):'Viewer');
   setFindingRunId(route.runId||null);
   setSelectedFinding(null);
   dispatchViewer({type:'reset',value:{
    findingId:route.findingId||null,positionMs:route.positionMs||0,
    interval:route.startMs!=null&&route.endMs!=null?{startMs:route.startMs,endMs:route.endMs}:null,
   }});
  };
  window.addEventListener('hashchange',sync);
  sync();
  return()=>window.removeEventListener('hashchange',sync);
 },[]);
 function setPage(next:string){const target=next as Exclude<AppPage,'NotFound'>;navigate(routeFor(target,caseIdRef.current,current?.id||selected,tab))}
 function openEvidence(e:Evidence){setSelected(e.id);setTab('Viewer');dispatchViewer({type:'reset'});setActiveChannel(null);navigate(routeFor('Workbench',caseId,e.id))}
 function openActivitySubject(evidenceId:string,runId?:string|null){setSelected(evidenceId);setFindingRunId(runId||null);setTab('Viewer');navigate(routeFor('Workbench',caseId,evidenceId,'Viewer',{runId}))}
 function updateFindingNotes(findingId:string,next:Note[]){setNotes(current=>[...current.filter(note=>note.findingId!==findingId),...next]);setAudit(current=>[{key:'session.reviewerNotesUpdated',params:{findingId}},...current])}
 async function addNote(f:Finding,action:string,text=''){const status=action.toLowerCase().includes('question')?'questioned':'reviewed',noteText=text||`Marked ${status} for analyst review.`;try{const note=API?await createReviewApi(apiBaseUrl).createNote(f.finding_id,{status,text:noteText},'Demo analyst'):{id:`LOCAL-${Date.now()}`,findingId:f.finding_id,text:noteText,status,at:new Date().toISOString(),author:'Demo analyst',authorVerified:false} as Note;updateFindingNotes(f.finding_id,[...notes.filter(item=>item.findingId===f.finding_id),note]);setModal(null)}catch(error){notify(error instanceof Error?error.message:'Review note could not be saved')}}
 function createPreviewUrl(file:File){const url=URL.createObjectURL(file);objectUrls.current.add(url);return url}
 async function intake(){if(!uploadFiles.length||uploading)return;setUploading(true);setEvidenceError('');try{
  if(API){
   for(const file of uploadFiles){
    const registered=await uploadCaseOriginal(caseId,file,{supplied_by:suppliedBy,collection_reference:collectionReference,note:receipt});
    setItems(items=>[...items.filter(item=>item.caseId!==caseId||item.id!==registered.evidence_id),evidenceFromApi(registered)]);
    setUploadFiles(files=>files.filter(item=>item!==file));
   }
   if(caseIdRef.current===caseId){setModal(null);setReceipt('');setSuppliedBy('');setCollectionReference('')}
   notify({key:'session.originalsPreserved'});
   return;
  }
  if(SERVER_INTAKE){
   if(uploadFiles.length!==1)throw new Error('Choose one JPEG, PNG or WebP image for server intake.');
   const record=await preserveEvidence(caseId,uploadFiles[0],receipt);
   setPreservedItems(previous=>[...previous.filter(item=>item.id!==record.id),record]);
   setAudit(previous=>[{key:'session.serverIntake',params:{evidenceId:record.id}},...previous]);
   if(caseIdRef.current===caseId){
    setUploadFiles([]);setReceipt('');setModal(null);openEvidence(record);
   }
   notify({key:'session.originalPreserved'});
   return;
  }
  for(const file of uploadFiles){if(!/\.(png|jpe?g|mp4|wav|mp3)$/i.test(file.name)||file.size>50*1024*1024)throw new Error('Use JPEG, PNG, MP4, WAV or MP3 up to 50 MB.');const bytes=await file.arrayBuffer();const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');const type=file.type.startsWith('video')||/\.mp4$/i.test(file.name)?'video':file.type.startsWith('audio')||/\.(wav|mp3)$/i.test(file.name)?'audio':'image';const registered=await caseSource.registerEvidence(caseId,{filename:file.name,media_type:type,role:'Evidence',size_bytes:file.size,sha256:hash},'Demo analyst');setItems(v=>[...v,{...evidenceFromApi(registered),source:createPreviewUrl(file),mime:file.type||type,sizeBytes:file.size}]);setAudit(v=>[{key:'session.inventoryRegistered',params:{filename:file.name,receipt:receipt||'—'}},...v]);if(registered.duplicate_hash_of.length)notify({key:'session.duplicateHash',params:{evidenceIds:registered.duplicate_hash_of.join(', ')}})}setModal(null);setUploadFiles([]);notify({key:'session.inventoryAdded'})}catch(e){const message=e instanceof Error?e.message:'Evidence registration failed';setEvidenceError(message);notify(message)}finally{setUploading(false)}}
 const zipRequest=useRef<{archive:File;title:string;description:string;key:string}|null>(null);
 async function createCase(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();
  setCaseSaving(true);
  setCasesError('');
  const form=new FormData(event.currentTarget);
  const title=String(form.get('title')).trim();
  const description=String(form.get('description')||'').trim();
  try{
   const archive=form.get('archive');
   let record:CaseRecord;
   if(archive instanceof window.File && archive.name){
    if(!API)throw new Error('Connect the case backend to upload a ZIP.');
    if(!archive.size || archive.size>64*1024*1024)throw new Error('Choose a nonempty ZIP up to 64 MiB.');
    const previous=zipRequest.current;
    const sameFile=previous?.archive.name===archive.name && previous.archive.size===archive.size &&
      previous.archive.lastModified===archive.lastModified;
    const key=sameFile && previous.title===title && previous.description===description
      ? previous.key : crypto.randomUUID();
    zipRequest.current={archive,title,description,key};
    const upload=new FormData();
    upload.set('file',archive);
    upload.set('title',title);
    upload.set('description',description);
    upload.set('request_key',key);
    const response=await fetch(apiBaseUrl.replace(/\/$/,'')+'/api/cases/from-zip',{method:'POST',body:upload});
    const body=await response.json().catch(()=>null);
    if(!response.ok || typeof body?.case_id!=='string'){
     throw new Error(typeof body?.detail==='string'?body.detail:'ZIP upload failed. Retry to resume the same request.');
    }
    record=await caseSource.getCase(body.case_id);
    zipRequest.current=null;
    notify('Case created. Automatic analysis started.');
   }else{
    record=await caseSource.createCase({title,description},'Demo analyst');
    notify({key:API?'session.persistentCaseCreated':'session.localCaseCreated'});
   }
   setCases(current=>[record,...current.filter(item=>item.id!==record.id)]);
   setModal(null);
   setAudit(current=>[{key:'session.caseCreated',params:{caseId:record.id}},...current]);
   navigate(routeFor('Overview',record.id));
  }catch(error){
   const message=error instanceof Error?error.message:'Case creation failed';
   setCasesError(message);
   notify(message);
  }finally{setCaseSaving(false);}
 }
 async function requestRun(){
  if(!current||scanning||runSubmissions.current.has(current.id))return;
  const item=current;
  runSubmissions.current.add(item.id);
  const base=import.meta.env.VITE_D1_API_BASE_URL?.trim()||apiBaseUrl;
  if(item.fixture&&FIXTURE){
   setScanning(true);
   const source=new MemoryRunSource(runs);
   const simulation=await import('../data/fixtureSimulation');
   const run=simulation.simulateFixtureRun(source,item,currentRuns.find(candidate=>candidate.findings.length)?.findings??[],simulationOutcome);
   source.subscribe(run.run_id,updated=>{setRuns(previous=>previous.map(candidate=>candidate.run_id===updated.run_id?updated:candidate));if(['completed','partial','failed','unsupported','cancelled'].includes(updated.execution_status)){setFindings(previous=>[...previous.filter(finding=>finding.run_id!==updated.run_id),...updated.findings]);setScanning(false);runSubmissions.current.delete(item.id)}});
   setRuns(previous=>[...previous,run]);setAudit(previous=>[{key:'session.fixtureRunRequested',params:{runId:run.run_id}},...previous]);setRunAnnouncement({key:'session.newRunQueued',params:{runId:run.run_id}});return;
  }
  if(!base){const source=new MemoryRunSource(runs),run=source.createRun({evidence:item});setRuns(previous=>[...previous,run]);setAudit(previous=>[{key:'session.analysisNotSent',params:{runId:run.run_id}},...previous]);setRunAnnouncement({key:'session.runRecordedFailed',params:{runId:run.run_id}});notify(run.errors[0].message);runSubmissions.current.delete(item.id);return}
  setScanning(true);
  setScanErrors(previous=>({...previous,[item.id]:''}));
  try{
   if(!base)throw new Error('Configure VITE_D1_API_BASE_URL to connect the detection service.');
   if(item.fixture)throw new Error('Add a media file to run a live scan.');
   const source=new ApiRunSource(base),run=await source.createRun(item);
   setRuns(previous=>[...previous.filter(candidate=>candidate.run_id!==run.run_id),run]);
   setAudit(previous=>[{key:'session.analysisQueued',params:{runId:run.run_id}},...previous]);setRunAnnouncement({key:'session.newRunQueued',params:{runId:run.run_id}});
   watchRun(source,run,()=>{setScanning(false);runSubmissions.current.delete(item.id)});
  }catch(error){
   const message=error instanceof Error?error.message:'Detection scan failed.';
   setScanErrors(previous=>({...previous,[item.id]:message}));
   setScanning(false);runSubmissions.current.delete(item.id);notify(message);
  }
 }
 async function retryRun(previous:RunRecord){
  const key=`retry:${previous.run_id}`;if(runSubmissions.current.has(key)||runs.some(run=>run.retry_of===previous.run_id&&(run.execution_status==='queued'||run.execution_status==='running')))return;runSubmissions.current.add(key);
  if(previous.fixture&&FIXTURE){const retry=createRetryRun(previous,{now:new Date().toISOString(),newId:createRunId()});setRuns(current=>[...current,retry]);const source=new MemoryRunSource([...runs,retry]);source.subscribe(retry.run_id,updated=>{setRuns(current=>current.map(run=>run.run_id===updated.run_id?updated:run));if(['completed','partial','failed','unsupported','cancelled'].includes(updated.execution_status))setFindings(current=>[...current.filter(finding=>finding.run_id!==updated.run_id),...updated.findings])});const simulation=await import('../data/fixtureSimulation');simulation.simulateExistingFixtureRun(source,retry,previous.findings,simulationOutcome);runSubmissions.current.delete(key);return}
  try{const source=new ApiRunSource(apiBaseUrl),retry=await source.retryRun(previous,caseId);setRuns(current=>[...current.filter(run=>run.run_id!==retry.run_id),retry]);setAudit(current=>[{key:'session.retryRequested',params:{oldRunId:previous.run_id,newRunId:retry.run_id,attempt:retry.attempt??1}},...current]);setRunAnnouncement({key:'session.retryQueued',params:{oldRunId:previous.run_id,newRunId:retry.run_id}});watchRun(source,retry,()=>runSubmissions.current.delete(key))}catch(error){runSubmissions.current.delete(key);notify(error instanceof Error?error.message:'Retry could not be created.')}
 }
 async function verifyCurrent(item:Evidence){
  if(verifying)return;
  setVerifying(true);
  try{
   const verification=await verifyEvidence(item.id);
   setPreservedItems(previous=>previous.map(record=>record.id===item.id?{...record,verification}:record));
   setAudit(previous=>[{key:'session.verification',params:{evidenceId:item.id,status:verification.status}},...previous]);
  }catch(error){notify((error as Error).message)}
  finally{setVerifying(false)}
 }
 function attachSample(item:Evidence){
  const next=[...new Set([...sampleIds,item.id])];
  try{localStorage.setItem('pratyaksh-sample-ids',JSON.stringify(next))}
  catch{notify({key:'session.saveSampleFailed'});return}
  setSampleIds(next);
  notify({key:'session.sampleAttached'});
 }
 const draftReport=activeCase?makeReportSnapshot(activeCase,reportVersion+1,preparer,reportSections,evidence,findings,caseNotes,caseProvenance?.case.id===caseId?caseProvenance:null):null;
 const report=selectedSnapshot||draftReport;
 function saveReport(){
  if(!draftReport)return;
  const next={...reportSnapshots,[caseId]:[...snapshots,draftReport]};
  try{localStorage.setItem('pratyaksh-report-snapshots',JSON.stringify(next))}
  catch{notify({key:'session.saveReportFailed'});return}
  setReportSnapshots(next);
  setSnapshotRevision(draftReport.revision);
  notify({key:'session.reportSaved'});
 }
 const visible=evidence.filter(e=>(filter==='All evidence'||e.type===filter.toLowerCase()||e.role===filter)&&(!query||`${e.id} ${e.name} ${e.hash}`.toLowerCase().includes(query.toLowerCase())));
 const channelTone=(fs:Finding[])=>fs.some(f=>tone(f)==='danger')?'danger':fs.some(f=>tone(f)==='warning')?'warning':fs.some(f=>tone(f)==='unavailable')?'unavailable':fs.some(f=>tone(f)==='intact')?'intact':'neutral';
 function EvidenceIcon({e}:{e:Evidence}){const I=iconFor(e.type),latest=newestFirst(runs.filter(run=>run.evidence_id===e.id))[0];return <><span className={'file-icon '+e.type}><I size={18}/></span>{latest&&<RunStatusBadge run={latest} compact/>}</>}
 function StatusDot({fs}:{fs:Finding[]}){return <span className={'channel-dot '+channelTone(fs)} title={fs.map(classification).join(', ')||'Not examined'}/>}
 function provenance(){return <><div className="panel-title"><div><h3>{translate("Available provenance")}</h3><p>{translate("Relationships in the supplied reference collection")}</p></div><Badge>{translate("FIXTURE DATA")}</Badge></div><div className="graph"><svg viewBox="0 0 660 280" role="img" aria-label={translate("Fixture provenance relationships")}><defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0 6 3 0 6" fill="#5f9995"/></marker></defs><path d="M190 125C260 125 260 125 330 125" fill="none" stroke="#608b92" strokeWidth="1.5" strokeDasharray="5 5"/><path d="M450 145C500 145 450 230 540 230" fill="none" stroke="#5f9995" strokeWidth="1.5" markerEnd="url(#arrow)"/><rect x="45" y="85" width="155" height="80" rx="7" className="graph-node"/><rect x="320" y="85" width="175" height="80" rx="7" className="graph-node active"/><rect x="475" y="205" width="145" height="60" rx="7" className="graph-node"/><g fill="#93a7b6" fontSize="11" fontFamily="monospace"><text x="62" y="108">{translate("REFERENCE")}</text><text x="339" y="108">{translate("EVIDENCE")}</text><text x="491" y="228">{translate("DERIVATIVE")}</text></g><g fill="#d8e3e9" fontSize="13"><text x="62" y="135">REF-001</text><text x="339" y="135">{current?.id||'EVID-001'}</text><text x="491" y="250">{translate("Sampled frame")}</text></g><text x="220" y="106" fill="#8197a9" fontSize="10">{translate("similarity candidate")}</text></svg></div><div className="graph-legend"><span><i className="dashed"/>{translate("Similarity candidate")}</span><span><i/>{translate("Application-created derivative")}</span></div><div className="notice"><Info size={15}/> {translate("A similarity relationship is not a verified edit history or the original source.")}</div><h4 className="section-label spaced">{translate("CONTENT CREDENTIALS")}</h4><div className="property-grid">{['Manifest present','Content binding','Signature valid','Signer trusted'].map((s,i)=><div key={s}><span>{s}</span><Badge t="neutral">{i===0?'Not present':'Not assessed'}</Badge></div>)}</div><p className="muted small">{translate("Fixture inspection · No C2PA validator executed. Missing credentials do not imply manipulation.")}</p></>}
 function reportPreview(){
  if(!report)return <p>{translate("Select a case to prepare a report.")}</p>;
  return <div className="paper">
   <div className="paper-brand"><BrandMark className="brand-mark"/><span>PRATYAKSH</span><small>{translate("FORENSIC REVIEW")}</small></div>
   <div className="paper-rule"/>
   <span className="paper-eyebrow">{translate("INVESTIGATION REPORT · REVISION")} {report.revision}</span>
   <h2>{report.case.title}</h2>
   <p className="paper-meta">{report.case.id} · {report.preparer||'Not specified'} · {report.generated_at}</p>
   <div className="paper-warning">{report.fixture?'Includes illustrative data':'Prototype evidence record'}</div>
   {report.sections.map((section,index)=><section key={section}>
    <h3>{index+1}. {section}</h3>
    {section==='Evidence inventory'&&report.evidence.map(item=><p key={item.id}>
     <b>{item.id}</b> · {item.name}<br/>
     SHA-256: {item.hash}<br/>{translate("Received:")} {item.received}
     {item.registeredBy&&<><br/>{translate("Registered by")} {item.registeredBy} {translate("(self-declared)")}</>}
     {item.receipt?.supplied_by&&<><br/>{translate("Supplied by (reported)")} {item.receipt.supplied_by}</>}
     {item.receipt?.collection_reference&&<><br/>{translate("Collection reference (reported)")} {item.receipt.collection_reference}</>}
     {item.receipt?.note&&<><br/>{translate("Receipt note")} {item.receipt.note}</>}
     {item.receiptContext&&<><br/>{translate("Receipt context:")} {item.receiptContext}</>}
     {item.verification&&<><br/>{translate("Stored file check:")} {item.verification.status} · {item.verification.checked_at}
     <br/>{translate("Observed SHA-256:")} {item.verification.actual_sha256||'Unavailable'}</>}
    </p>)}
    {section==='Forensic findings'&&report.provenance&&<>
     <h4>{translate("Case provenance")}</h4>
     <p>{report.provenance.analysis_id} {translate("· SHA-256")} {report.provenance.report_sha256}</p>
     {report.provenance.relationships.length?report.provenance.relationships.map(edge=>{
      const left=report.provenance?.images.find(item=>item.id===edge.left_id);
      const right=report.provenance?.images.find(item=>item.id===edge.right_id);
      return <p key={edge.id}><b>{left?.case_evidence_id||edge.left_id} ↔ {right?.case_evidence_id||edge.right_id}</b> · {edge.explanation}
       {edge.support?.frame_timestamps_ms&&<> {translate("Sampled timestamps:")} {edge.support.frame_timestamps_ms.join(' ms / ')} {translate("ms.")}</>}
      </p>;
     }):<p>{translate("No supported relationships recorded in this analysis.")}</p>}
     {report.provenance.images.map(item=><p key={item.id}>
      <b>{item.case_evidence_id||item.id} · {item.filename}</b><br/>
      SHA-256 {item.sha256}<br/>
      {item.metadata_status} {Object.entries(item.metadata||{}).map(([key,value])=>key+' '+value).join(' · ')}<br/>
      {translate("Content Credentials")} {item.credentials?.status||'unavailable'} {translate("· signature")} {item.credentials?.signature||'unavailable'} {translate("· binding")} {item.credentials?.content_binding||'unavailable'} {translate("· signer")} {item.credentials?.signer_trust||'unavailable'}<br/>
      {item.credentials?.trust_policy&&<>{item.credentials.trust_policy}<br/></>}
      {item.comparison_area&&<>{translate("Selected area")} {item.comparison_area.map(value=>(value*100).toFixed(1)+'%').join(', ')} {translate("(left, top, right, bottom)")}<br/></>}
      {item.video_coverage&&<>{translate("Examined timestamps")} {item.video_coverage.examined_timestamps_ms.join(', ')} {translate("ms ·")} {item.video_coverage.source_frame_timestamps} {translate("recorded frame timestamps")}</>}
     </p>)}
     {(report.provenance.review_notes||[]).map((note,index)=><p key={index}>
      {translate("Provenance reviewer note ·")} {note.author} · {note.scope_id||'whole analysis'} · {note.text}
     </p>)}
     {report.provenance.limitations.map(limit=><p key={limit}>{limit}</p>)}
    </>}
    {section==='Methods and scope'&&<p>{report.case.description}</p>}
    {section==='Forensic findings'&&(report.findings.length?report.findings.map(finding=><p key={finding.finding_id}>
     <b>{finding.finding_id}</b> · {finding.evidence_id} · {finding.run_id}<br/>
     {classification(finding)} · {finding.observation}<br/>
     {translate("Method:")} {finding.method} ({finding.method_version}{translate(") · Scope:")} {finding.scope}<br/>
     {finding.score&&<>{translate("Raw score:")} {finding.score.value} · {finding.score.positive_class} · {finding.score.calibration_status}<br/></>}
     {finding.support_refs.length>0&&<>{translate("Supporting references:")} {finding.support_refs.join(', ')}<br/></>}
     {finding.limitations.join(' ')}
    </p>):<p>{translate("No findings recorded.")}</p>)}
    {section==='Analyst notes'&&(report.notes.length?report.notes.map(note=><p key={note.id}>
     {note.findingId} · {note.at} · {note.status} · {note.author} {translate("(self-declared):")} {note.text}
    </p>):<p>{translate("No analyst notes recorded.")}</p>)}
    {section==='Limitations'&&report.limitations.map(limit=><p key={limit}>{limit}</p>)}
   </section>)}
   <footer>{report.case.id} {translate("· PRATYAKSH")}</footer>
  </div>;
 }

 return <div className="app-root"><AppShell page={page} caseId={activeCase&&['Overview','Evidence','Workbench','MediaAnalysis','ReviewReport','Audit'].includes(page)?caseId:undefined} evidenceCount={evidence.length} reportCount={reportVersion} query={query} fixture={FIXTURE&&!API} connected={API} light={light} brand={<BrandMark className="brand-mark"/>} onHome={onHome} onNavigate={setPage} onQuery={value=>{setQuery(value);if(value&&activeCase)setPage('Evidence')}} onTheme={()=>setLight(value=>!value)} onHelp={()=>setModal('help')}>
 {casesLoading&&<div className="notice"><Loader2 size={15} className="spin"/>{translate("Loading cases from the server…")}</div>}
 {casesError&&<div className="notice"><TriangleAlert size={15}/>{translate("Case service error:")} {casesError}</div>}
 {evidenceLoading&&<div className="notice"><Loader2 size={15} className="spin"/>{translate("Loading evidence inventory…")}</div>}
 {caseLookupError&&<div className="notice" role="alert">{caseLookupError} <button type="button" onClick={()=>setCaseReload(value=>value+1)}>{translate("Reload case")}</button></div>}
 {runStatusError&&<div className="notice" role="alert">{runStatusError} <button type="button" onClick={()=>setCaseReload(value=>value+1)}>{translate("Refresh run status")}</button></div>}
 {evidenceError&&<div className="notice"><TriangleAlert size={15}/>{translate("Evidence inventory error:")} {evidenceError}</div>}
 {API&&!casesLoading&&!casesError&&!cases.length&&<div className="notice"><Info size={15}/>{translate("No server cases yet. Create an investigation to begin.")}</div>}
 {page==='ReviewReport'&&!activeCase&&routePath==='/review'&&<>
   <PageHeading eyebrow={translate("INVESTIGATION")} title="Review & Report" subtitle="Choose a case to understand findings, review limitations and prepare a referenced report."/>
   <section className="panel evaluation-empty"><FileText size={28}/>
     <h2>{translate(cases.length?'Select a case':'Create a case to get started')}</h2>
     {cases.map(record=><button key={record.id} className="button secondary" onClick={()=>navigate(routeFor('ReviewReport',record.id))}>{record.title}</button>)}
     {!cases.length&&<button className="button primary" onClick={()=>setModal('case')}>{translate("New case")}</button>}
   </section>
 </>}
 {page==='Provenance'&&<ProvenanceLab key={[parseHash(window.location.hash).caseId,parseHash(window.location.hash).analysisId,parseHash(window.location.hash).relationshipId].join(':')||'standalone'} initialCaseId={parseHash(window.location.hash).caseId} initialAnalysisId={parseHash(window.location.hash).analysisId} initialRelationshipId={parseHash(window.location.hash).relationshipId} caseEvidence={API&&parseHash(window.location.hash).caseId?evidence.filter(item=>item.preserved):undefined} baseUrl={import.meta.env.VITE_D1_API_BASE_URL?.trim()||apiBaseUrl}/>}
 {page==='MediaAnalysis'&&<MediaAnalysis baseUrl={import.meta.env.VITE_D1_API_BASE_URL?.trim()||apiBaseUrl} cases={cases} activeCase={activeCase} evidence={evidence} findings={findings} onCase={id=>navigate(id?routeFor('MediaAnalysis',id):'/analysis')} onOpen={openEvidence} onAdd={()=>activeCase?setModal('upload'):navigate('/cases')}/>}
 {page==='ReviewReport'&&activeCase&&<ReviewReport briefing={<CaseBriefingPanel key={caseId} caseId={caseId} enabled={API&&!activeCase.fixture} recordsVersion={JSON.stringify({findings,runs:caseRuns.map(run=>[run.run_id,run.execution_status,run.findings]),evidence:evidence.map(item=>item.id)})}/>} caseRecord={activeCase} evidence={evidence} findings={findings} notes={caseNotes} onReview={finding=>addNote(finding,'reviewed')} onOpenFinding={finding=>{setSelected(finding.evidence_id);setFindingRunId(finding.run_id);setTab('Viewer');navigate(routeFor('Workbench',caseId,finding.evidence_id,'Viewer',{findingId:finding.finding_id,runId:finding.run_id}))}} reportBuilder={API?<ReportsWorkspace key={caseId} caseId={caseId} baseUrl={apiBaseUrl}/>:undefined}/>}
 {page==='Cases'&&<CaseList baseUrl={API?apiBaseUrl:undefined} hasReport={id=>(reportSnapshots[id]?.length??0)>0} cases={cases} evidenceFor={id=>[...(API?items.filter(item=>item.caseId===id):evidenceForCase(items,id)),...preservedItems.filter(item=>item.caseId===id)]} findingsFor={id=>FIXTURE&&id==='CASE-2026-014'?findings:[]} onOpen={id=>navigate(routeFor('Overview',id))} onCreate={()=>setModal('case')}/>}
 {page==='NotFound'&&<RouteNotFound path={routePath} onCases={()=>navigate('/cases')}/>}
 {page!=='NotFound'&&page!=='Cases'&&['Overview','Evidence','Workbench'].includes(page)&&!activeCase&&(!API||(resolvedCaseId===caseId&&!caseLookupError))&&<CaseNotFound caseId={caseId} onCases={()=>navigate('/cases')}/>}
 {activeCase&&['Overview','Evidence','Workbench'].includes(page)&&<><div className="page-heading"><div><div className="eyebrow">{translate("INVESTIGATION /")} <span className="mono">{caseId}</span></div><h1>{page==='Workbench'?'Media Analysis':page==='Evidence'?'Evidence library':'Case overview'}</h1><p>{page==='Workbench'?'Review four separate technical channels for this evidence.':page==='Evidence'?'Preserved records and supporting material for this investigation.':'Every piece of evidence. One connected investigation.'}</p></div><div className="heading-actions"><button className="button secondary" onClick={()=>setModal('case')}><Plus size={15}/>{translate("New case")}</button><button className="button primary" onClick={()=>setModal('upload')}><Upload size={15}/>{translate("Add evidence")}</button></div></div><div className="case-header"><div className="case-header-main"><span className="case-folder"><FolderOpen size={22}/></span><div><button className="case-title" onClick={()=>setMenu(v=>!v)}>{activeCase.title}<ChevronDown size={16}/></button><p><span className="mono">{caseId}</span><span>•</span>{translate("Created")} {activeCase.created}<span>•</span>{translate("Demo analyst")}</p>{menu&&<div className="case-menu">{cases.map(c=><button key={c.id} onClick={()=>{setMenu(false);navigate(routeFor('Overview',c.id))}}><Folder size={15}/><span>{c.title}<small>{c.id}</small></span>{c.id===caseId&&<Check size={14}/>}</button>)}</div>}</div></div><Badge t="intact">{activeCase.status}</Badge></div><div className="case-tabs">{[{label:'Overview',page:'Overview'},{label:'Evidence',page:'Evidence'},{label:'Review & Report',page:'ReviewReport'}].map(item=><button key={item.page} className={page===item.page||item.page==='Evidence'&&page==='Workbench'?'active':''} onClick={()=>setPage(item.page)}>{item.label}{item.page==='Evidence'&&<span>{evidence.length}</span>}</button>)}<div className="case-tabs-right"><Lock size={12}/>{translate("Local single-user prototype")}</div></div></>}
 {API&&activeCase&&['Overview','MediaAnalysis','ReviewReport'].includes(page)&&
  <CaseAutomationProgress key={caseId} caseId={caseId} baseUrl={apiBaseUrl} onUpdated={()=>setCaseReload(value=>value+1)}/>}
 {page==='Overview'&&activeCase&&<>
  <section className="panel case-details-panel"><div><span className="eyebrow">{translate("CASE DETAILS")}</span><h2>{activeCase.title}</h2><p>{activeCase.description||'No case description recorded.'}</p></div><dl><div><dt>{translate("Case ID")}</dt><dd className="mono">{activeCase.id}</dd></div><div><dt>{translate("Status")}</dt><dd>{activeCase.status}</dd></div><div><dt>{translate("Created")}</dt><dd>{activeCase.created}</dd></div><div><dt>{translate("Analyst")}</dt><dd>{translate("Demo analyst")}</dd></div></dl><div className="case-entry-links"><button className="button secondary" disabled={!current} onClick={()=>{if(current){setSelected(current.id);setTab('Provenance');navigate(routeFor('Workbench',caseId,current.id,'provenance'))}}}><GitBranch size={15}/>{translate("Provenance")}</button><button className="button secondary" onClick={()=>setPage('ReviewReport')}><FileText size={15}/>Review & Report</button></div></section>
  <ProcessingSummary summary={processing} compact/>
  {API&&<RecentActivity caseId={caseId} baseUrl={apiBaseUrl} onViewAll={()=>setPage('Audit')} onOpen={openActivitySubject}/>}
  <div className="summary-grid"><div className="summary-card"><div className="summary-top"><span>{translate("Evidence items")}</span><Layers size={17}/></div><div className="summary-number">{evidence.length.toString().padStart(2,'0')}<small>{translate("in this investigation")}</small></div><div className="summary-foot">{evidence.filter(e=>e.type==='video').length} {translate("video")} <i/> {evidence.filter(e=>e.type==='audio').length} {translate("audio")} <i/> {evidence.filter(e=>e.type==='image').length} {translate("images")}</div></div><div className="summary-card"><div className="summary-top"><span>{translate("Review required")}</span><Target size={17}/></div><div className="summary-number">{evidence.filter(e=>e.status==='Review required').length.toString().padStart(2,'0')}<small>{translate("evidence items flagged")}</small></div><div className="summary-foot"><span className="status-pip amber"/>{translate(processing.fixture?"Within examined fixture scope":"Within recorded assessment scope")}</div></div><div className="summary-card"><div className="summary-top"><span>{translate("Integrity records")}</span><ShieldCheck size={17}/></div><div className="summary-number">{findings.filter(f=>f.category==='integrity').length.toString().padStart(2,'0')}<small>{translate("intake comparisons")}</small></div><div className="summary-foot"><span className="status-pip teal"/>{translate(processing.fixture?"Unchanged since fixture intake":"Unchanged since intake")}</div></div><div className="summary-card"><div className="summary-top"><span>{translate("Analyst notes")}</span><FileText size={17}/></div><div className="summary-number">{caseNotes.length.toString().padStart(2,'0')}<small>{translate("review annotations")}</small></div><div className="summary-foot">{translate("Machine findings remain unchanged")}</div></div></div>
  <div className="overview-grid"><section className="panel evidence-panel"><div className="panel-heading"><div><h2>{translate("Case evidence")} <span>{evidence.length}</span></h2>{API&&<button className="button subtle" onClick={()=>navigate(`/cases/${encodeURIComponent(caseId)}/provenance`)}>{translate("Compare preserved evidence")}{caseProvenance?` · ${caseProvenance.relationships.length} links`:''}</button>}<p>{translate("Review media and examine each result channel independently.")}</p></div><button className="button subtle" onClick={()=>setPage('Evidence')}>{translate("View all")}<ArrowUpRight size={14}/></button></div><EvidenceTable evidence={visible} findings={findings} onOpen={openEvidence} onProvenance={item=>{if(item.preserved){navigate(`/cases/${encodeURIComponent(caseId)}/provenance`);return}setSelected(item.id);setTab('Provenance');navigate(routeFor('Workbench',caseId,item.id,'provenance'))}} onReports={()=>setPage('ReviewReport')} onAdd={()=>setModal('upload')}/></section><aside className="right-column">{!API&&<section className="panel activity-panel"><div className="panel-heading"><h2>{translate("Case activity")}</h2><button className="icon-button" aria-label={translate("View audit log")} onClick={()=>setPage('Audit')}><ArrowUpRight size={15}/></button></div>{caseId==='CASE-2026-014'?<div className="activity-timeline">{[{icon:FileCheck,title:'Fixture run completed',detail:'RUN-003 · 4 separate channels',time:'10:24 UTC',color:'teal'},{icon:GitBranch,title:'Reference added',detail:'REF-001 · Interview recording',time:'10:02 UTC',color:''},{icon:Upload,title:'Evidence intake recorded',detail:'3 initial fixture evidence items',time:'09:46 UTC',color:''},{icon:FolderOpen,title:'Investigation opened',detail:'Demo analyst created this case',time:'09:40 UTC',color:''}].map((a,i)=><div className="activity-event" key={i}><span className={'activity-icon '+a.color}><a.icon size={14}/></span><div><h4>{a.title}</h4><p>{a.detail}</p><time>{a.time}</time></div></div>)}</div>:<div className="empty compact"><History size={24}/><h3>{translate("No case activity")}</h3><p>{translate("Browser-local actions for this case will appear here.")}</p></div>}<button className="activity-link" onClick={()=>setPage('Audit')}>{translate("View full audit trail")}<ArrowRight size={14}/></button></section>}<section className="report-callout"><span className="report-icon"><FileText size={21}/></span><h3>{translate("Bring the findings together.")}</h3><p>{translate("Prepare a traceable report with examined scope, methods and limitations.")}</p><button className="button secondary full" onClick={()=>setPage('ReviewReport')}>Review & Report<ArrowRight size={15}/></button></section></aside></div>
  <div className="bottom-note"><Shield size={15}/><span>{translate("Four channels. Separate conclusions.")}</span><p>{translate("An intact file confirms preservation since intake; it does not establish that its content is genuine.")}</p><button onClick={()=>setPage('Methods')}>{translate("Read methods & limits")}<ArrowUpRight size={13}/></button></div>
 </>}
 {page==='Evidence'&&activeCase&&<><ProcessingSummary summary={processing}/><section className="panel evidence-inventory"><div className="panel-heading"><h2>{translate("Evidence inventory")}</h2><div className="segmented">{['All evidence','Video','Audio','Image','Reference'].map(v=><button key={v} className={filter===v?'active':''} onClick={()=>setFilter(v)}>{v}</button>)}</div></div><EvidenceTable evidence={visible} findings={findings} runs={runs} onOpen={openEvidence} onProvenance={item=>{if(item.preserved){navigate(`/cases/${encodeURIComponent(caseId)}/provenance`);return}setSelected(item.id);setTab('Provenance');navigate(routeFor('Workbench',caseId,item.id,'provenance'))}} onReports={()=>setPage('ReviewReport')} onAdd={()=>setModal('upload')}/></section></>}
 {page==='Workbench'&&(current?<><div className="workbench detection-workbench"><aside className="evidence-tree"><div className="tree-heading">{translate("EVIDENCE TREE")}<span>{evidence.length}</span></div><div className="tree-case"><FolderOpen size={15}/>{caseId}</div>{evidence.map(e=><button key={e.id} className={'tree-item '+(current.id===e.id?'active':'')} onClick={()=>navigate(routeFor('Workbench',caseId,e.id,tab))}><EvidenceIcon e={e}/><span><strong>{e.id}</strong><small>{e.name}</small><span className="tree-dots">{channels.map(c=><StatusDot key={c.key} fs={findings.filter(f=>f.evidence_id===e.id&&f.category===c.key)}/>)}</span></span></button>)}<button className="tree-add" onClick={()=>setModal('upload')}><Plus size={14}/>{translate("Add evidence")}</button><div className="tree-caption"><Lock size={13}/>{translate("Original files are never used as analysis working copies.")}</div></aside><section className="viewer-panel"><div className="viewer-header"><div><strong>{current.name}</strong><span className="mono">{current.id}</span></div><button className="icon-button" aria-label={translate("Show file details")} onClick={()=>setTab('Metadata')}><Info size={17}/></button></div><div className="viewer-tabs">{['Viewer','Inspection','Metadata','Provenance','Compare'].map(t=><button key={t} className={tab===t?'active':''} onClick={()=>setTab(t)}>{t}</button>)}</div>{tab==='Viewer'?<EvidenceViewer evidence={current} findings={currentFindings} selection={viewerSelection} dispatch={dispatchViewer} coverage={(currentRuns.find(run=>run.run_id===activeFindingRun)||currentRun)?.coverage||null} apiMode={API}/>:tab==='Inspection'?<VisualInspection key={current.id} evidence={current} positionMs={viewerSelection.positionMs}/>:tab==='Metadata'?<div className="metadata-view"><div className="panel-title"><h3>{translate("File examination")}</h3><Badge>{current.fixture?'Fixture metadata':'Browser intake'}</Badge></div><div className="property-list">{[['Evidence ID',current.id],['Filename',current.name],['Media type',current.type],['Dimensions / stream',current.dimensions],['Size',current.size],['Received at',current.received],['Source',current.fixture?'Precomputed fixture':'Browser session upload'],['Declared software','Unavailable'],['Raw metadata timezone','Unknown']].map(([k,v])=><div key={k}><span>{k}</span><strong>{v}</strong></div>)}</div><h4>{translate("SHA-256 reference")}</h4><div className="full-hash mono">{current.hash}</div><div className="notice"><Info size={14}/>{translate("Metadata is descriptive. It does not independently prove origin or authenticity.")}</div></div>:tab==='Provenance'?<div className="provenance-view">{current.fixture?provenance():<div className="empty"><GitBranch size={28}/><h3>{translate("Case provenance")}</h3>{current.preserved?<button className="button secondary" onClick={()=>navigate(`/cases/${encodeURIComponent(caseId)}/provenance`)}>{translate("Compare preserved evidence")}</button>:<p>{translate("Preserve case originals to compare them here.")}</p>}</div>}</div>:<ReferenceComparison key={current.id} evidence={current} items={evidence}/>}</section><DetectionWorkspace key={current.id} evidence={current} findings={currentFindings} selectedFindingId={viewerSelection.findingId}
 detectionBaseUrl={import.meta.env.VITE_D1_API_BASE_URL?.trim()||apiBaseUrl} onReport={()=>setPage('ReviewReport')} onRun={requestRun} scanning={scanning} scan={scans[current.id]} scanError={scanErrors[current.id]}
 onVerify={current.source?.startsWith('/api/evidence/')?()=>verifyCurrent(current):undefined}
 verifying={verifying}
 onAttachSample={FIXTURE&&current.source?.startsWith('/api/evidence/')&&!sampleIds.includes(current.id)?()=>attachSample(current):undefined}
 renderFindings={(layerFindings,layerChannels)=><FindingsPanel findings={layerFindings} channels={layerChannels} runs={currentRuns} notes={notes} selectedRunId={activeFindingRun} onSelectRun={setFindingRunId} onSelect={(model,index=0)=>{setTab('Viewer');const chip=model.locations[index]||model.locations[0];dispatchViewer({type:"finding",findingId:model.id,positionMs:chip?.positionMs||0,interval:chip?.startMs!=null&&chip?.endMs!=null?{startMs:chip.startMs,endMs:chip.endMs}:null,regionId:chip?.regionId||null});setSelectedFinding(currentFindings.find(item=>item.finding_id===model.id)||null)}} onTechnical={setTechnical} apiBaseUrl={API?apiBaseUrl:''} onNotesChange={updateFindingNotes}/>}/></div>
 {FIXTURE&&<label className="simulation-selector">{translate("Fixture outcome")}<select value={simulationOutcome} onChange={event=>setSimulationOutcome(event.target.value as SimulationOutcome)}>{['completed','partial','failed','unsupported','cancelled'].map(value=><option key={value}>{value}</option>)}</select></label>}
 <RunHistoryPanel runs={currentRuns} retryContext={{fileAvailable:Boolean(current.source)||current.fixture,backendConnected:Boolean(import.meta.env.VITE_D1_API_BASE_URL?.trim()||apiBaseUrl),fixtureMode:current.fixture&&FIXTURE}} onRetry={retryRun} onViewFindings={id=>setFindingRunId(id)}/><div className="sr-only" aria-live="polite">{runAnnouncement&&messageText(runAnnouncement)}</div></>:<div className="empty"><Layers size={30}/><h3>{translate("No evidence to examine")}</h3><p>{translate("Add a file to this case to begin.")}</p><button className="button primary" onClick={()=>setModal('upload')}>{translate("Add evidence")}</button></div>)}
 {page==='Evaluation'&&<Evaluation/>}
 {page==='Audit'&&activeCase&&<CaseAuditView caseId={caseId} baseUrl={apiBaseUrl} onOpen={openActivitySubject}/>}
 {page==='Audit'&&!activeCase&&(!API||(resolvedCaseId===caseId&&!caseLookupError))&&routePath.startsWith('/cases/')&&<CaseNotFound caseId={caseId} onCases={()=>navigate('/cases')}/>}
 {page==='Methods'&&<><PageHeading eyebrow="TRANSPARENCY" title={translate("Methods & limits")} subtitle="The workflow is consolidated, but every technical method retains its own scope, result and limitation."/><div className="panel"><div className="panel-heading"><h2>{translate("Capability register")}</h2><Badge>{translate("Frontend prototype")}</Badge></div><div className="capability-table"><table><thead><tr><th>{translate("Workflow")}</th><th>{translate("Technical capability")}</th><th>{translate("Implementation")}</th><th>{translate("Examined scope")}</th></tr></thead><tbody>{[['Media Analysis','AI-generation signals','Unavailable','No inference backend connected'],['Media Analysis','Manipulation, editing and file integrity','Planned','Separate tampering findings and SHA-256 comparisons'],['Provenance & Comparison','Source relationships and credential checks','Prototype','Single-file provenance plus multi-file relationship analysis'],['Review & Report','Referenced explanation and analyst review','Implemented','Summary statements are derived only from recorded findings'],['Review & Report','Saved reports and exports','Implemented','Reviewed revisions, JSON/ZIP export and printable reports']].map(row=><tr key={row.join(':')}>{row.map((v,i)=><td key={i}>{i===2?<Badge t={v==='Unavailable'?'unavailable':'neutral'}>{v}</Badge>:v}</td>)}</tr>)}</tbody></table></div></div><div className="method-grid">{[['Integrity is a reference comparison','An intake hash can establish whether the bytes changed since that reference was recorded. It cannot establish that the content is genuine.'],['Provenance is available history','Missing credentials are neutral. Signature validity, content binding and signer trust are different checks.'],['Scores are not universal probabilities','A raw detector score needs its positive class, range, scope and calibration status. No combined authenticity score is provided.'],['Review preserves machine findings','Summary edits and analyst notes remain separate from recorded machine findings and retain their references.']].map(([title,body])=><section className="panel" key={title}><Shield size={20}/><h3>{title}</h3><p>{body}</p></section>)}</div></>}
 {page==='Audit'&&!activeCase&&!routePath.startsWith('/cases/')&&<><PageHeading eyebrow="ACCOUNTABILITY" title={translate("Audit log")} subtitle="A readable record of this browser session and the fixture scenario."/><section className="panel"><div className="panel-heading"><h2>{translate("Workspace activity")}</h2><button className="button secondary" onClick={()=>download('pratyaksh-session-audit.json',JSON.stringify({fixture:FIXTURE,events:audit.map(message=>messageText(message,'en')),notes},null,2))}><Download size={14}/>{translate("Export log")}</button></div>{[...audit,...(FIXTURE?[{key:'session.fixtureFindingsLoaded'} as UiMessage,{key:'session.fixtureReferenceAdded'} as UiMessage,{key:'session.fixtureCaseCreated'} as UiMessage]:[])].map((message,i)=>{const fixture='key' in message&&message.key.startsWith('session.fixture');return <div className="audit-row" key={i}><span className="audit-event-icon"><History size={16}/></span><span><strong>{messageText(message)}</strong><small>{translate(fixture?'session.fixtureEvent':'session.browserAction')}</small></span><Badge>{translate(fixture?'session.fixtureBadge':'session.localBadge')}</Badge></div>})}</section><p className="muted small">{translate("Browser logs are not a protected chain of custody. Operational audit storage requires a secured backend.")}</p></>}
 {page==='Settings'&&<><PageHeading eyebrow="WORKSPACE" title={translate("Workspace settings")} subtitle="A transparent view of this prototype’s environment and behavior."/><section className="panel settings-panel"><h3>{translate("Environment")}</h3><div className="property-list">{[['Workspace',API?'Persistent case inventory':'Local single-user prototype'],['Identity','Demo analyst · self-declared, not authenticated'],['Fixture mode',FIXTURE?'Enabled through VITE_DEV_FIXTURE':'Disabled'],['Backend connection',backendHealth],['Case records',API?'SQLite server persistence':'Browser localStorage only'],['Uploaded media',API?'Originals preserved on the server when uploaded to a case':SERVER_INTAKE?'Supported images preserved by the local intake service':'Browser session only']].map(([k,v])=><div key={k}><span>{k}</span><strong>{v}</strong></div>)}</div><h3>{translate("Appearance")}</h3><button className="button secondary" onClick={()=>setLight(v=>!v)}>{light?<Moon size={15}/>:<Sun size={15}/>}{translate("Use")} {light?'dark':'light'} {translate("theme")}</button></section></>}
 <footer className="app-footer"><span>PRATYAKSH <span className="footer-sep">/</span> {translate("Clarity through examination.")}</span><span><span className="status-pip teal"/>{translate("Workspace ready")} <span className="footer-sep">/</span> {translate("v0.1.0")}</span></footer>
 </AppShell>
 {toast&&<div className="toast" role="status"><Info size={16}/>{messageText(toast)}<button className="icon-button" aria-label={translate("Dismiss notification")} onClick={()=>setToast(null)}><X size={14}/></button></div>}
 {modal&&<div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)setModal(null)}}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close icon-button" aria-label={translate("Close dialog")} onClick={()=>setModal(null)}><X size={19}/></button>{modal==='upload'?<><span className="modal-icon"><Upload size={23}/></span><h2 id="modal-title">{translate("Add evidence")}</h2><p>{translate("Record media for this investigation.")}</p><div className="notice"><Info size={15}/>{API?'Files are preserved once and available for case analysis and provenance.':SERVER_INTAKE?'The local evidence service preserves the original image and records its intake hash.':'Browser intake only. Files stay in this session; server preservation and forensic analysis are not connected.'}</div><input ref={fileRef} type="file" multiple={API||!SERVER_INTAKE} accept={API?".jpg,.jpeg,.png,.webp,.heic,.heif,.mp4,.wav,.mp3":SERVER_INTAKE?".jpg,.jpeg,.png,.webp":".jpg,.jpeg,.png,.mp4,.wav,.mp3"} hidden onChange={e=>setUploadFiles(Array.from(e.target.files||[]))}/><button className="dropzone" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();setUploadFiles(Array.from(e.dataTransfer.files))}} onClick={()=>fileRef.current?.click()}><Upload size={25}/><strong>{translate("Drop evidence here, or browse files")}</strong><span>{API?'JPEG, PNG, WebP, HEIC, MP4, WAV or MP3 · up to 15 MiB each':SERVER_INTAKE?'JPEG, PNG or WebP · one image, up to 15 MiB':'JPEG, PNG, MP4, WAV or MP3 · up to 50 MB each'}</span></button>{uploadFiles.map(f=><div className="upload-selected" key={f.name}><File size={16}/><span>{f.name}</span><small>{(f.size/1024/1024).toFixed(2)} {translate("MB")}</small></div>)}{API&&<>
   <label className="field">{translate("Supplied by (optional)")}<input maxLength={200} value={suppliedBy} onChange={event=>setSuppliedBy(event.target.value)}/></label>
   <label className="field">{translate("Collection reference (optional)")}<input maxLength={200} value={collectionReference} onChange={event=>setCollectionReference(event.target.value)}/></label>
  </>}<label className="field">{translate("Receipt context")}<textarea placeholder={translate("How and where was this media received?")} maxLength={1000} value={receipt} onChange={e=>setReceipt(e.target.value)}/></label><p className="muted small">{translate("Client checks are convenience only. Operational intake requires authoritative server validation.")}</p><button className="button primary full" disabled={!uploadFiles.length||uploading||!caseId} onClick={intake}>{uploading?<Loader2 size={16} className="spin"/>:<Hash size={16}/>}{API?'Preserve evidence':SERVER_INTAKE?'Preserve image & record SHA-256':'Calculate SHA-256 & add to session'}</button></>:modal==='case'?<form onSubmit={createCase}><span className="modal-icon"><FolderPlusIcon/></span><h2 id="modal-title">{translate("Create an investigation")}</h2><p>{translate("A dedicated workspace for evidence and findings.")}</p><label className="field">{translate("Case title")}<input name="title" placeholder={translate("e.g. Suspected payment impersonation")} required maxLength={100}/></label><label className="field">{translate("Case context")}<textarea name="description" placeholder={translate("Describe the complaint and examination questions.")}/></label>{API&&<label className="field">Evidence ZIP (optional)
  <input type="file" name="archive" accept=".zip,application/zip" disabled={caseSaving} onChange={()=>{zipRequest.current=null;}}/>
  <small>Up to 12 media files. Analysis starts automatically.</small>
 </label>}{casesError&&<p role="alert">{casesError}</p>}<div className="notice"><Lock size={15}/>{API?'Case metadata persists in SQLite. Creator identity is self-declared.':'Case metadata is stored in this browser.'}</div><button className="button primary full" type="submit" disabled={caseSaving}>{caseSaving?<Loader2 size={15} className="spin"/>:<Plus size={15}/>}{translate("Create case")}</button></form>:modal==='note'&&selectedFinding?<form onSubmit={e=>{e.preventDefault();addNote(selectedFinding,'Annotated',String(new FormData(e.currentTarget).get('note')))}}><h2 id="modal-title">{translate("Add analyst note")}</h2><p className="mono">{selectedFinding.finding_id} · {selectedFinding.evidence_id}</p><blockquote>{selectedFinding.observation}</blockquote><label className="field">{translate("Your observation")}<textarea name="note" placeholder={translate("Record your interpretation, question or next step…")} required/></label><p className="muted small">{translate("This creates a separate review record. The machine finding remains unchanged.")}</p><button className="button primary full">{translate("Save note")}</button></form>:modal==='details'?<><h2 id="modal-title">{activeCase?.title}</h2><p>{activeCase?.description}</p><div className="property-list"><div><span>{translate("Case ID")}</span><strong>{caseId}</strong></div><div><span>{translate("Identity")}</span><strong>{translate("Demo analyst")}</strong></div><div><span>{translate("Context")}</span><strong>{translate("Fictional investigation scenario")}</strong></div></div></>:<><h2 id="modal-title">{translate("A workspace for careful examination.")}</h2><p>{translate("Start with a case, open an evidence item, then review synthetic-media, tampering, integrity and provenance results separately.")}</p><div className="notice"><FlaskConical size={16}/>{translate("All seeded findings are fixtures. The interface does not run forensic models or certify authenticity.")}</div><button className="button primary full" onClick={()=>{setModal(null);setPage('Methods')}}>{translate("Read methods & limits")}<ArrowRight size={15}/></button></>}</section></div>}
 <TechnicalDetailsDrawer finding={technical} onClose={()=>setTechnical(null)}/>
 </div>
}
function AppInner(){
 useI18n();
 const [workspace,setWorkspace]=useState(()=>Boolean(window.location.hash)&&!window.location.hash.startsWith('#/personal'));
 const [personal,setPersonal]=useState(()=>window.location.hash.startsWith('#/personal'));
 const [launchModal,setLaunchModal]=useState<string|null>(null);
 const firstCase=()=>{if(apiBaseUrl)return undefined;try{return (JSON.parse(localStorage.getItem('pratyaksh-cases')||'null') as CaseRecord[]|null)?.[0]?.id}catch{return undefined}};
 const openProfessional=(path='/cases')=>{setPersonal(false);setLaunchModal(null);setWorkspace(true);navigate(path)};
 const returnHome=()=>{history.replaceState(null,'',window.location.pathname+window.location.search);setWorkspace(false);setPersonal(false);setLaunchModal(null)};
 if(personal)return <PersonalApp onHome={returnHome} onProfessional={()=>openProfessional('/cases')}/>;
 if(!workspace)return <Landing onPersonal={()=>{setPersonal(true);window.location.hash='/personal/check'}} onProvenance={()=>openProfessional('/provenance')} onAnalyse={()=>openProfessional('/cases')} onReport={()=>{const id=firstCase();openProfessional(id?routeFor('ReviewReport',id):'/cases')}}/>;
 return <InvestigationApp initialModal={launchModal} onHome={returnHome}/>;
}
function App(){return <I18nProvider><AppInner/></I18nProvider>}
function PageHeading({eyebrow,title,subtitle}:{eyebrow:string;title:string;subtitle:string}){return <div className="page-heading standalone"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div></div>}
function FolderPlusIcon(){return <FolderOpen size={23}/>}
export default App;
