import {parseViewerUrlState} from '../viewer/urlState';
export type AppPage='Cases'|'MediaAnalysis'|'Provenance'|'ReviewReport'|'Overview'|'Evidence'|'Workbench'|'Methods'|'Audit'|'Settings'|'Evaluation'|'NotFound';

export type AppRoute={
  page:AppPage;
  path:string;
  caseId?:string;
  evidenceId?:string;
  tab?:string;
  positionMs?:number;
  startMs?:number;
  endMs?:number;
  findingId?:string;
  runId?:string;
  layer?:string;
  redirectTo?:string;
  analysisId?:string;
  relationshipId?:string;
};

const clean=(hash:string)=>{
  const raw=hash.replace(/^#/, '')||'/';
  const [pathname,query='']=raw.split('?');
  return {pathname:pathname.startsWith('/')?pathname:`/${pathname}`,params:new URLSearchParams(query)};
};

export function parseHash(hash:string):AppRoute{
  const {pathname,params}=clean(hash);
  const parts=pathname.split('/').filter(Boolean).map(decodeURIComponent);
  if(parts.length===1&&parts[0]==='cases')return {page:'Cases',path:pathname};
  if(parts[0]==='cases'&&parts[1]){
    const base={caseId:parts[1],path:pathname};
    if(parts.length===2)return {...base,page:'Overview'};
    if(parts[2]==='analysis'&&parts.length===3)return {...base,page:'MediaAnalysis'};
    if(parts[2]==='review'&&parts.length===3)return {...base,page:'ReviewReport'};
    if(parts[2]==='evidence'&&parts[3])return {...base,page:'Workbench',evidenceId:parts[3],tab:params.get('tab')||undefined,findingId:params.get('finding')||undefined,runId:params.get('run')||undefined,layer:params.get('layer')||undefined,...parseViewerUrlState(params)};
    if(parts[2]==='evidence'&&parts.length===3)return {...base,page:'Evidence'};
    if(parts[2]==='provenance'&&parts.length===3)return {...base,page:'Provenance',analysisId:params.get('analysis')||undefined,relationshipId:params.get('relationship')||undefined};
    if(parts[2]==='reports'&&parts.length===3)return {...base,page:'ReviewReport',redirectTo:`/cases/${encodeURIComponent(parts[1])}/review`};
    if(parts[2]==='audit'&&parts.length===3)return {...base,page:'Audit'};
  }
  if(parts.length===1&&['detection','deepfake-detection','authentication','authentication-tampering','file-integrity','integrity'].includes(parts[0]))return {page:'MediaAnalysis',path:pathname,redirectTo:'/analysis'};
  if(parts.length===1&&['explainability','explainable-ai','ai-summary','case-summary','analyst-review','report-generation','reports'].includes(parts[0]))return {page:'ReviewReport',path:pathname,redirectTo:'/review'};
  const global:Record<string,AppPage>={analysis:'MediaAnalysis',provenance:'Provenance',review:'ReviewReport',methods:'Methods',audit:'Audit',settings:'Settings',evaluation:'Evaluation'};
  if(parts.length===1&&global[parts[0]])return {page:global[parts[0]],path:pathname};
  return {page:'NotFound',path:pathname};
}

export function routeFor(page:Exclude<AppPage,'NotFound'>,caseId?:string,evidenceId?:string,tab?:string,state?:{findingId?:string|null;runId?:string|null;layer?:string|null}):string{
  if(page==='Cases')return '/cases';
  if(page==='MediaAnalysis')return caseId?`/cases/${encodeURIComponent(caseId)}/analysis`:'/analysis';
  if(page==='Provenance')return caseId?`/cases/${encodeURIComponent(caseId)}/provenance`:'/provenance';
  if(page==='ReviewReport')return caseId?`/cases/${encodeURIComponent(caseId)}/review`:'/review';
  if(page==='Audit'&&caseId)return `/cases/${encodeURIComponent(caseId)}/audit`;
  if(page==='Methods'||page==='Audit'||page==='Settings'||page==='Evaluation')return `/${page.toLowerCase()}`;
  if(!caseId)return '/cases';
  if(page==='Overview')return `/cases/${encodeURIComponent(caseId)}`;
  if(page==='Evidence')return `/cases/${encodeURIComponent(caseId)}/evidence`;
  const params=new URLSearchParams();if(tab)params.set('tab',tab.toLowerCase());if(state?.findingId)params.set('finding',state.findingId);if(state?.runId)params.set('run',state.runId);if(state?.layer)params.set('layer',state.layer);const suffix=params.size?`?${params}`:'';
  return `/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId||'')}${suffix}`;
}

export function hasKnownCase(route:AppRoute,caseIds:readonly string[]):boolean{
  return !route.caseId||caseIds.includes(route.caseId);
}

export function navigate(path:string):void{
  const next=path.startsWith('/')?path:`/${path}`;
  if(window.location.hash.slice(1)!==next)window.history.pushState(null,'',`#${next}`);
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}
