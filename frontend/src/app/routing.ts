export type AppPage='Cases'|'Overview'|'Evidence'|'Workbench'|'Reports'|'Methods'|'Audit'|'Settings'|'Evaluation'|'NotFound';

export type AppRoute={
  page:AppPage;
  path:string;
  caseId?:string;
  evidenceId?:string;
  tab?:string;
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
    if(parts[2]==='evidence'&&parts[3])return {...base,page:'Workbench',evidenceId:parts[3],tab:params.get('tab')||undefined};
    if(parts[2]==='evidence'&&parts.length===3)return {...base,page:'Evidence'};
    if(parts[2]==='reports'&&parts.length===3)return {...base,page:'Reports'};
  }
  const global:Record<string,AppPage>={methods:'Methods',audit:'Audit',settings:'Settings',evaluation:'Evaluation'};
  if(parts.length===1&&global[parts[0]])return {page:global[parts[0]],path:pathname};
  return {page:'NotFound',path:pathname};
}

export function routeFor(page:Exclude<AppPage,'NotFound'>,caseId?:string,evidenceId?:string,tab?:string):string{
  if(page==='Cases')return '/cases';
  if(page==='Methods'||page==='Audit'||page==='Settings'||page==='Evaluation')return `/${page.toLowerCase()}`;
  if(!caseId)return '/cases';
  if(page==='Overview')return `/cases/${encodeURIComponent(caseId)}`;
  if(page==='Evidence')return `/cases/${encodeURIComponent(caseId)}/evidence`;
  if(page==='Reports')return `/cases/${encodeURIComponent(caseId)}/reports`;
  const suffix=tab?`?tab=${encodeURIComponent(tab.toLowerCase())}`:'';
  return `/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId||'')}${suffix}`;
}

export function hasKnownCase(route:AppRoute,caseIds:readonly string[]):boolean{
  return !route.caseId||caseIds.includes(route.caseId);
}

export function navigate(path:string):void{
  const next=path.startsWith('/')?path:`/${path}`;
  if(window.location.hash.slice(1)===next)window.dispatchEvent(new HashChangeEvent('hashchange'));
  else{
    window.location.hash=next;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }
}
