import {useEffect,useMemo,useRef,useState} from 'react';
import {ArrowLeft,CheckCircle2,ChevronRight,CircleHelp,Download,FileAudio,FileImage,FileVideo,GitCompareArrows,History,Info,LockKeyhole,Menu,ScanSearch,Shield,ShieldAlert,Trash2,Upload,X,XCircle} from 'lucide-react';
import {BrandMark} from '../components/BrandMark';
import {summaryTextIsAllowed} from '../review/summaryPolicy';
import './personal.css';

type PersonalPage='check'|'compare'|'history'|'help';
type SavedCheck={id:string;kind:'file'|'compare';title:string;result:string;detail:string;createdAt:string};

const pageFromHash=():PersonalPage=>{
  const value=window.location.hash.replace(/^#\/personal\/?/,'').split('?')[0];
  return value==='compare'||value==='history'||value==='help'?value:'check';
};
const mediaKind=(file:File)=>file.type.startsWith('image/')?'photo':file.type.startsWith('video/')?'video':file.type.startsWith('audio/')?'voice message':'file';
const fileIcon=(file:File)=>file.type.startsWith('image/')?FileImage:file.type.startsWith('video/')?FileVideo:file.type.startsWith('audio/')?FileAudio:FileImage;
const shortSize=(bytes:number)=>bytes<1024*1024?`${Math.max(1,Math.round(bytes/1024))} KB`:`${(bytes/1024/1024).toFixed(1)} MB`;
const digest=async(file:File)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))).map(value=>value.toString(16).padStart(2,'0')).join('');

function FilePreview({file}:{file:File}){
  const [url,setUrl]=useState('');
  useEffect(()=>{const next=URL.createObjectURL(file);setUrl(next);return()=>URL.revokeObjectURL(next)},[file]);
  if(!url)return null;
  if(file.type.startsWith('image/'))return <img className="personal-media" src={url} alt={`Preview of ${file.name}`}/>;
  if(file.type.startsWith('video/'))return <video className="personal-media" src={url} controls/>;
  if(file.type.startsWith('audio/'))return <audio className="personal-audio" src={url} controls/>;
  return null;
}

function PrivacyNote(){
  return <aside className="personal-privacy"><LockKeyhole size={19}/><div><strong>Your file stays in this browser in Personal mode</strong><p>This preview does not upload or permanently store the file. Only a small check summary is saved in this browser under “My checks”, and you can delete it there.</p></div></aside>;
}

function ResultCard({title,detail,next}:{title:string;detail:string;next:string}){
  return <section className="personal-result uncertain" aria-live="polite"><div className="result-icon"><CircleHelp size={25}/></div><div><span>SHOULD I BE CONCERNED?</span><h2>{title}</h2><p>{detail}</p><div className="next-step"><strong>What should I do next?</strong><p>{next}</p></div></div></section>;
}

export function PersonalApp({onProfessional,onHome}:{onProfessional:()=>void;onHome:()=>void}){
  const [page,setPage]=useState<PersonalPage>(pageFromHash);
  const [drawer,setDrawer]=useState(false);
  const [file,setFile]=useState<File|null>(null);
  const [comparison,setComparison]=useState<File[]>([]);
  const [checking,setChecking]=useState(false);
  const [checkDone,setCheckDone]=useState(false);
  const [compareResult,setCompareResult]=useState<{same:boolean;hashes:string[]}|null>(null);
  const [saved,setSaved]=useState<SavedCheck[]>(()=>{try{return JSON.parse(localStorage.getItem('pratyaksh-personal-checks')||'[]')}catch{return[]}});
  const fileInput=useRef<HTMLInputElement>(null);
  const compareInput=useRef<HTMLInputElement>(null);
  useEffect(()=>{const sync=()=>setPage(pageFromHash());window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync)},[]);
  useEffect(()=>{localStorage.setItem('pratyaksh-personal-checks',JSON.stringify(saved))},[saved]);
  const go=(next:PersonalPage)=>{window.location.hash=`/personal/${next}`;setPage(next);setDrawer(false)};
  const record=(entry:Omit<SavedCheck,'id'|'createdAt'>)=>setSaved(current=>[{...entry,id:crypto.randomUUID(),createdAt:new Date().toISOString()},...current]);
  const runCheck=()=>{
    if(!file)return;
    setChecking(true);
    window.setTimeout(()=>{
      setChecking(false);setCheckDone(true);
      record({kind:'file',title:file.name,result:'We couldn’t tell',detail:'No supported live analysis was available for this check.'});
    },650);
  };
  const runCompare=async()=>{
    if(comparison.length<2)return;
    setChecking(true);
    const hashes=await Promise.all(comparison.map(digest));
    const same=hashes.every(value=>value===hashes[0]);
    setCompareResult({same,hashes});setChecking(false);
    record({kind:'compare',title:`${comparison.length} files compared`,result:same?'These files are exact copies':'We didn’t find enough evidence to connect these files',detail:same?'Every byte matches.':'The files are not byte-for-byte identical; visual-region comparison is not available in this preview.'});
  };
  const downloadSummary=(title:string,body:string)=>{
    const safeTitle=summaryTextIsAllowed(title)?title:'We couldn’t tell';
    const blob=new Blob([`PRATYAKSH PERSONAL SUMMARY\n\n${safeTitle}\n\n${body}\n\nGenerated ${new Date().toLocaleString()}\nThis summary is not an authenticity determination.`],{type:'text/plain'});
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='pratyaksh-summary.txt';link.click();URL.revokeObjectURL(url);
  };
  const comparisonPreviews=useMemo(()=>comparison.filter(item=>item.type.startsWith('image/')).slice(0,2),[comparison]);
  const pageLabel={check:'Check a file',compare:'Compare copies',history:'My checks',help:'Help'}[page];
  return <div className={`personal-app ${drawer?'nav-open':''}`}>
    <a className="skip-link" href="#personal-main">Skip to content</a>
    {drawer&&<button className="personal-nav-scrim" aria-label="Close navigation" onClick={()=>setDrawer(false)}/>} 
    <aside className="personal-sidebar" aria-label="Personal navigation">
      <button className="personal-brand" onClick={onHome}><BrandMark className="brand-mark"/><span>PRATYAKSH<small>MULTIMEDIA FORENSICS</small></span></button>
      <button className="personal-nav-close" aria-label="Close navigation" onClick={()=>setDrawer(false)}><X size={18}/></button>
      <div className="personal-workspace-switch"><span><Shield size={18}/></span><div>Personal workspace<small>Simple media checks</small></div></div>
      <span className="personal-nav-label">PERSONAL</span>
      <nav><button className={page==='check'?'active':''} onClick={()=>go('check')}><ScanSearch size={18}/>Check a file</button><button className={page==='compare'?'active':''} onClick={()=>go('compare')}><GitCompareArrows size={18}/>Compare copies</button><button className={page==='history'?'active':''} onClick={()=>go('history')}><History size={18}/>My checks{saved.length>0&&<span className="personal-nav-count">{saved.length}</span>}</button></nav>
      <span className="personal-nav-label second">RESOURCES</span>
      <nav><button className={page==='help'?'active':''} onClick={()=>go('help')}><CircleHelp size={18}/>Help</button></nav>
      <div className="personal-sidebar-bottom"><div className="personal-secure-note"><LockKeyhole size={15}/><div>Your files stay local<small>Browser-only Personal mode</small></div></div><button className="personal-profile" onClick={onProfessional}><span className="personal-avatar">PRO</span><span>Professional mode<small>Investigation workspace</small></span><ChevronRight size={16}/></button></div>
    </aside>
    <div className="personal-main-shell">
      <header className="personal-topbar"><button className="personal-mobile-menu" aria-label="Open navigation" onClick={()=>setDrawer(true)}><Menu size={19}/></button><div className="personal-breadcrumb"><span>Personal workspace</span><ChevronRight size={13}/><strong>{pageLabel}</strong></div><div className="personal-topbar-right"><span className="personal-environment"><i/>LOCAL PROCESSING</span><button className="professional-link" onClick={onProfessional}>Professional mode</button><span className="personal-top-avatar">P</span></div></header>
      <main id="personal-main"><div className="personal-mode-banner"><Shield size={14}/><strong>PERSONAL MODE</strong><span>Simple guidance · technical details stay in professional mode</span><span className="banner-end">PRATYAKSH 2026</span></div>
      {page==='check'&&<div className="personal-flow"><div className="personal-hero"><span>CHECK A FILE</span><h1>Check a suspicious photo, video or voice message</h1><p>Upload a file to look for signs of AI generation or editing. We identify its type automatically.</p></div><PrivacyNote/>
        <section className="personal-card upload-card"><input ref={fileInput} hidden type="file" accept="image/*,video/*,audio/*" onChange={event=>{setFile(event.target.files?.[0]||null);setCheckDone(false)}}/>{!file?<button className="personal-drop" onClick={()=>fileInput.current?.click()}><Upload size={28}/><strong>Choose a photo, video or voice message</strong><span>JPEG, PNG, WebP, MP4, WAV or MP3</span></button>:<><div className="selected-personal-file">{(()=>{const Icon=fileIcon(file);return <Icon size={22}/>})()}<div><strong>{file.name}</strong><span>{mediaKind(file)} · {shortSize(file.size)}</span></div><button aria-label="Remove file" onClick={()=>{setFile(null);setCheckDone(false)}}><Trash2 size={18}/></button></div><FilePreview file={file}/>{!checkDone&&<button className="personal-primary" disabled={checking} onClick={runCheck}>{checking?'Checking available methods…':'Check this file'}</button>}</>}</section>
        {checkDone&&file&&<><ResultCard title="We couldn’t tell" detail="The file type and available file information were read, but no supported live AI-generation or manipulation analysis was available. No authenticity conclusion has been made." next="Keep the original file and verify its claim through another source. If the message asks for urgent payment or personal information, contact the person through a number you already trust."/><section className="personal-details"><article><span>WHAT WE CHECKED</span><h3>File type and available file information</h3><p>The file was recognized as a {mediaKind(file)}.</p></article><article><span>WHAT WE FOUND</span><h3>No supported analysis result</h3><p>We do not show a score when the underlying method cannot support a conclusion.</p></article><article><span>WHAT WE COULDN’T CHECK</span><h3>AI-generation and manipulation signals</h3><p>The analysis service needed for these checks was unavailable in this Personal mode preview.</p></article></section><button className="download-summary" onClick={()=>downloadSummary('We couldn’t tell',`File: ${file.name}\nChecked: file type and available information\nCould not check: AI-generation and manipulation signals`)}><Download size={17}/>Download summary</button></>}
      </div>}
      {page==='compare'&&<div className="personal-flow"><div className="personal-hero"><span>COMPARE COPIES</span><h1>See whether files match</h1><p>Upload two or more versions. We will first check whether they are exact copies and explain what stronger comparisons are available.</p></div><PrivacyNote/><section className="personal-card upload-card"><input ref={compareInput} hidden multiple type="file" accept="image/*,video/*,audio/*" onChange={event=>{setComparison(Array.from(event.target.files||[]));setCompareResult(null)}}/><button className="personal-drop compact" onClick={()=>compareInput.current?.click()}><GitCompareArrows size={28}/><strong>Choose two or more files</strong><span>Files are compared inside your browser</span></button>{comparison.map(item=><div className="selected-personal-file" key={`${item.name}-${item.lastModified}`}><div><strong>{item.name}</strong><span>{mediaKind(item)} · {shortSize(item.size)}</span></div></div>)}{comparisonPreviews.length>0&&<div className="side-by-side">{comparisonPreviews.map(item=><FilePreview key={`${item.name}-preview`} file={item}/>)}</div>}<button className="personal-primary" disabled={comparison.length<2||checking} onClick={runCompare}>{checking?'Comparing files…':'Compare files'}</button></section>
        {compareResult&&<><ResultCard title={compareResult.same?'These files are exact copies':'We didn’t find enough evidence to connect these files'} detail={compareResult.same?'The complete file contents match byte for byte.':'The files are not exact copies. This preview cannot yet compare matching image regions, crops or edits, so it does not claim that they are unrelated.'} next={compareResult.same?'Keep either original and confirm the claim it accompanies. Matching files do not establish whether the depicted content is genuine.':'Keep the original versions. A professional comparison can examine crops, matching regions and source relationships.'}/><button className="download-summary" onClick={()=>downloadSummary(compareResult.same?'These files are exact copies':'We didn’t find enough evidence to connect these files',comparison.map((item,index)=>`${item.name}: ${compareResult.hashes[index]}`).join('\n'))}><Download size={17}/>Download summary</button></>}
      </div>}
      {page==='history'&&<div className="personal-flow"><div className="personal-hero"><span>MY CHECKS</span><h1>Your saved summaries</h1><p>Only these summaries are saved in this browser. The uploaded media files are not retained by Personal mode.</p></div>{saved.length?<div className="personal-history">{saved.map(item=><article key={item.id}><span className="history-icon"><History size={18}/></span><div><strong>{item.result}</strong><h2>{item.title}</h2><p>{item.detail}</p><time>{new Date(item.createdAt).toLocaleString()}</time></div><button aria-label={`Delete ${item.title}`} onClick={()=>setSaved(current=>current.filter(entry=>entry.id!==item.id))}><Trash2 size={18}/></button></article>)}</div>:<section className="personal-empty"><History size={30}/><h2>No saved checks yet</h2><p>Checks you complete will appear here without storing the media itself.</p><button className="personal-primary" onClick={()=>go('check')}>Check a file</button></section>}</div>}
      {page==='help'&&<div className="personal-flow"><div className="personal-hero"><span>HELP</span><h1>Use results as one piece of evidence</h1><p>PRATYAKSH can identify technical signals, but a file check alone cannot verify every claim, person or event.</p></div><div className="help-grid"><article><ShieldAlert/><h2>If a message feels urgent</h2><p>Pause before paying, sharing credentials or installing software. Contact the person or organization through a phone number or website you already trust.</p></article><article><CheckCircle2/><h2>Keep the original</h2><p>Forwarding, screenshots and social-media downloads can remove useful information. Save the earliest available copy.</p></article><article><Info/><h2>Understand the wording</h2><p>“No suspicious signs found” never guarantees authenticity. “We couldn’t tell” means the available method or evidence could not support a conclusion.</p></article><article><XCircle/><h2>Delete your summaries</h2><p>Open My checks and use the delete button. Personal mode does not retain the media file after you leave or reload the page.</p></article></div><button className="back-professional" onClick={onProfessional}><ArrowLeft size={16}/>Open professional workspace</button></div>}
      </main>
    </div>
  </div>;
}
