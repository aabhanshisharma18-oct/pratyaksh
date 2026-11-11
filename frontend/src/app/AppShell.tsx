import React,{useEffect,useState} from 'react';
import {Activity,BookOpen,ChevronRight,CircleHelp,FileText,FlaskConical,FolderOpen,History,Layers,Lock,Menu,MoreHorizontal,Moon,Search,Settings2,Shield,Sun,X} from 'lucide-react';
import {AppPage} from './routing';
import {useI18n} from '../i18n';

type Props={
  page:AppPage;
  caseId?:string;
  evidenceCount:number;
  reportCount:number;
  query:string;
  fixture:boolean;
  light:boolean;
  brand:React.ReactNode;
  children:React.ReactNode;
  onHome:()=>void;
  onNavigate:(page:Exclude<AppPage,'NotFound'>)=>void;
  onQuery:(query:string)=>void;
  onTheme:()=>void;
  onHelp:()=>void;
};

export function AppShell({page,caseId,evidenceCount,reportCount,query,fixture,light,brand,children,onHome,onNavigate,onQuery,onTheme,onHelp}:Props){
  const {language,setLanguage,t}=useI18n();
  const [drawer,setDrawer]=useState(false);
  useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==='Escape')setDrawer(false)};window.addEventListener('keydown',close);return()=>window.removeEventListener('keydown',close)},[]);
  const go=(target:Exclude<AppPage,'NotFound'>)=>{onNavigate(target);setDrawer(false)};
  const global=[{page:'Cases' as const,label:'Cases',icon:FolderOpen},{page:'Evaluation' as const,label:'Evaluation',icon:Activity}];
  const scoped=[{page:'Overview' as const,label:'Overview',icon:FolderOpen},{page:'Evidence' as const,label:'Evidence',icon:Layers},{page:'Reports' as const,label:'Reports',icon:FileText}];
  const resources=[{page:'Methods' as const,label:'Methods & limits',icon:BookOpen},{page:'Audit' as const,label:'Audit log',icon:History},{page:'Settings' as const,label:'Settings',icon:Settings2}];
  const nav=(items:typeof global|typeof scoped|typeof resources)=>items.map(item=><button key={item.page} aria-current={page===item.page||item.page==='Evidence'&&page==='Workbench'?'page':undefined} className={page===item.page||item.page==='Evidence'&&page==='Workbench'?'active':''} onClick={()=>go(item.page)}><item.icon size={18}/>{t(item.label)}{item.page==='Evidence'&&<span className="nav-count">{evidenceCount}</span>}{item.page==='Reports'&&reportCount>0&&<span className="nav-count">{reportCount}</span>}</button>);
  return <div className={`app ${drawer?'nav-open':''}`}>
    {drawer&&<button className="nav-scrim" aria-label={t('Close navigation')} onClick={()=>setDrawer(false)}/>} 
    <aside className="sidebar" aria-label="Primary navigation">
      <button className="brand" onClick={onHome}>{brand}<span>PRATYAKSH<small>MULTIMEDIA FORENSICS</small></span></button>
      <button className="mobile-nav-close icon-button" aria-label={t('Close navigation')} onClick={()=>setDrawer(false)}><X size={18}/></button>
      <div className="workspace-switch"><span className="workspace-icon"><Shield size={18}/></span><div>{t('Investigation workspace')}<small>{t('Local prototype')}</small></div></div>
      <span className="nav-label">{t('Workspace').toUpperCase()}</span><nav>{nav(global)}</nav>
      {caseId&&<><span className="nav-label second">{caseId}</span><nav>{nav(scoped)}</nav></>}
      <span className="nav-label second">RESOURCES</span><nav>{nav(resources)}</nav>
      <div className="sidebar-bottom"><div className="secure-note"><Lock size={15}/><div>Your workspace, contained.<small>Browser-local demo session</small></div></div><button className="profile" onClick={()=>go('Settings')}><span className="avatar">DA</span><span>Demo analyst<small>Single-user workspace</small></span><MoreHorizontal size={18}/></button></div>
    </aside>
    <div className="app-main">
      <header className="topbar"><button className="mobile-menu icon-button" aria-label={t('Menu')} onClick={()=>setDrawer(true)}><Menu size={19}/></button><div className="breadcrumb"><span>{t('Workspace')}</span><ChevronRight size={13}/><strong>{t(page==='Workbench'?'Evidence':page)}</strong></div><label className="global-search"><Search size={16}/><input aria-label={t('Search evidence, IDs, hashes…')} placeholder={t('Search evidence, IDs, hashes…')} value={query} onChange={event=>onQuery(event.target.value)}/><kbd>⌘ K</kbd></label><div className="topbar-right"><span className="environment"><span/>{t('Local prototype')}</span><button className="language-toggle" onClick={()=>setLanguage(language==='en'?'hi':'en')} aria-label="Switch language">{language==='en'?'हिन्दी':'EN'}</button><button className="icon-button" title={t('Switch theme')} aria-label={t('Switch theme')} onClick={onTheme}>{light?<Moon size={17}/>:<Sun size={17}/>}</button><button className="icon-button" aria-label={t('Help')} onClick={onHelp}><CircleHelp size={18}/></button><span className="top-avatar">DA</span></div></header>
      <main><div className="fixture-banner"><FlaskConical size={14}/><strong>{t(fixture?'DEVELOPMENT FIXTURE · illustrative, not measured':'FRONTEND PROTOTYPE')}</strong><span>{t(fixture?'Precomputed fictional states · No live forensic analysis':'Analysis backend not connected')}</span><span className="banner-end">SUTRAM 2026 <span> / </span> PS02</span></div>{children}</main>
    </div>
  </div>;
}
