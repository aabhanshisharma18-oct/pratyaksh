import {translate} from '../i18n';
import React,{useEffect,useState} from 'react';
import {Activity,BookOpen,ChevronRight,CircleHelp,FileText,FlaskConical,FolderOpen,GitBranch,History,Layers,Lock,Menu,MoreHorizontal,Moon,ScanSearch,Search,Settings2,Shield,Sun,X} from 'lucide-react';
import {AppPage} from './routing';
import {useI18n,type MessageKey} from '../i18n';
import {LanguageSwitcher} from '../components/LanguageSwitcher';

type Props={
  page:AppPage;
  caseId?:string;
  evidenceCount:number;
  reportCount:number;
  query:string;
  fixture:boolean;
  connected:boolean;
  light:boolean;
  brand:React.ReactNode;
  children:React.ReactNode;
  onHome:()=>void;
  onNavigate:(page:Exclude<AppPage,'NotFound'>)=>void;
  onQuery:(query:string)=>void;
  onTheme:()=>void;
  onHelp:()=>void;
};

export function AppShell({page,caseId,evidenceCount,reportCount,query,fixture,connected,light,brand,children,onHome,onNavigate,onQuery,onTheme,onHelp}:Props){
  const {t}=useI18n();
  const [drawer,setDrawer]=useState(false);
  useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==='Escape')setDrawer(false)};window.addEventListener('keydown',close);return()=>window.removeEventListener('keydown',close)},[]);
  const go=(target:Exclude<AppPage,'NotFound'>)=>{onNavigate(target);setDrawer(false)};
  const global=[{page:'Cases' as const,label:'nav.cases' as MessageKey,icon:FolderOpen},{page:'MediaAnalysis' as const,label:'nav.mediaAnalysis' as MessageKey,icon:ScanSearch},{page:'Provenance' as const,label:'nav.provenanceComparison' as MessageKey,icon:GitBranch},{page:'ReviewReport' as const,label:'nav.reviewReport' as MessageKey,icon:FileText},{page:'Evaluation' as const,label:'nav.evaluation' as MessageKey,icon:Activity}];
  const scoped=[{page:'Overview' as const,label:'nav.overview' as MessageKey,icon:FolderOpen},{page:'Evidence' as const,label:'nav.evidence' as MessageKey,icon:Layers}];
  const resources=[{page:'Methods' as const,label:'nav.methodsLimits' as MessageKey,icon:BookOpen},{page:'Settings' as const,label:'nav.settings' as MessageKey,icon:Settings2}];
  const nav=(items:typeof global|typeof scoped|typeof resources)=>items.map(item=>{const active=page===item.page||item.page==='MediaAnalysis'&&page==='Workbench'||item.page==='Evidence'&&page==='Evidence';return <button key={item.page} aria-current={active?'page':undefined} className={active?'active':''} onClick={()=>go(item.page)}><item.icon size={18}/>{t(item.label)}{item.page==='Evidence'&&<span className="nav-count">{evidenceCount}</span>}{item.page==='ReviewReport'&&reportCount>0&&<span className="nav-count">{reportCount}</span>}</button>});
  return <div className={`app ${drawer?'nav-open':''}`}><a className="skip-link" href="#main-content">{t('nav.skipToContent')}</a>
    {drawer&&<button className="nav-scrim" aria-label={t('nav.closeNavigation')} onClick={()=>setDrawer(false)}/>}
    <aside className="sidebar" aria-label={t('nav.primary')}>
      <button className="brand" onClick={onHome}>{brand}<span>PRATYAKSH<small>{t('app.multimediaForensics').toUpperCase()}</small></span></button>
      <button className="mobile-nav-close icon-button" aria-label={t('nav.closeNavigation')} onClick={()=>setDrawer(false)}><X size={18}/></button>
      <div className="workspace-switch"><span className="workspace-icon"><Shield size={18}/></span><div>{t('app.investigationWorkspace')}<small>{t('app.localPrototype')}</small></div></div>
      <span className="nav-label">{t('nav.workspace').toUpperCase()}</span><nav>{nav(global)}</nav>
      {caseId&&<><span className="nav-label second">{caseId}</span><nav>{nav(scoped)}</nav></>}
      <span className="nav-label second">{t('nav.resources').toUpperCase()}</span><nav>{nav(resources)}</nav>
      <div className="sidebar-bottom"><div className="secure-note"><Lock size={15}/><div>{t('app.workspaceContained')}<small>{t('app.browserSession')}</small></div></div><button className="profile" onClick={()=>go('Settings')}><span className="avatar">DA</span><span>{t('app.demoAnalyst')}<small>{t('app.singleUserWorkspace')}</small></span><MoreHorizontal size={18}/></button></div>
    </aside>
    <div className="app-main">
      <header className="topbar"><button className="mobile-menu icon-button" aria-label={t('nav.openMenu')} onClick={()=>setDrawer(true)}><Menu size={19}/></button><div className="breadcrumb"><span>{t('nav.workspace')}</span><ChevronRight size={13}/><strong>{t(page==='Workbench'||page==='MediaAnalysis'?'nav.mediaAnalysis':page==='Provenance'?'nav.provenanceComparison':page==='ReviewReport'?'nav.reviewReport':page==='Cases'?'nav.cases':page==='Evaluation'?'nav.evaluation':page==='Overview'?'nav.overview':page==='Evidence'?'nav.evidence':page==='Audit'?'nav.auditLog':page==='Methods'?'nav.methodsLimits':'nav.settings')}</strong></div><label className="global-search"><Search size={16}/><input aria-label={t('app.searchPlaceholder')} placeholder={t('app.searchPlaceholder')} value={query} onChange={event=>onQuery(event.target.value)}/><kbd>{translate("⌘ K")}</kbd></label><div className="topbar-right"><span className="environment"><span/>{t('app.localPrototype')}</span><LanguageSwitcher variant="app"/><button className="icon-button" title={t('app.switchTheme')} aria-label={t('app.switchTheme')} onClick={onTheme}>{light?<Moon size={17}/>:<Sun size={17}/>}</button><button className="icon-button" aria-label={t('common.help')} onClick={onHelp}><CircleHelp size={18}/></button><span className="top-avatar">DA</span></div></header>
      <main id="main-content" tabIndex={-1}>{!connected&&!['MediaAnalysis','Provenance','ReviewReport'].includes(page)&&<div className="fixture-banner"><FlaskConical size={14}/><strong>{t(fixture?'DEVELOPMENT FIXTURE · illustrative, not measured':'FRONTEND PROTOTYPE')}</strong><span>{t(fixture?'Precomputed fictional states · No live forensic analysis':'Analysis backend not connected')}</span><span className="banner-end">SUTRAM 2026 <span> / </span> PS02</span></div>}{children}</main>
    </div>
  </div>;
}
