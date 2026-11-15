import {translate} from '../i18n';
import {scoreMeaning} from '../data/scoreMeaning';
import {useEffect, useRef, useState, type FormEvent} from 'react';
import {Download, FolderOpen, Image, Loader2, Minus, Plus, ScanSearch} from 'lucide-react';
import {scanLocalFile, type DetectionScan} from '../data/detectionScan';
import {classification, download, tone} from '../model';
import {fileInformation, filterLabels, imageFilterGroups, inspectBytes, inspectPixels, type ImageFilter, type InspectionResult} from './imageInspection';
import {VideoInspection} from './VideoInspection';
import {VoiceInspection} from './VoiceInspection';
import {FaceAnalysisViewer} from './FaceAnalysisViewer';
import {ShadowInspection, type ShadowLine} from './ShadowInspection';
import {InspectionComparison, InspectionOutput} from './InspectionOutput';
import './detectionLab.css';

const bookmarkGroups = [
  ['Integrity Analysis', [...imageFilterGroups[0][1], ...imageFilterGroups[1][1], ...imageFilterGroups[3][1]]],
  ['Global Processing Analysis', imageFilterGroups[2][1]],
  ['Local Tampering Analysis', imageFilterGroups[4][1]],
  ['Geometrical Analysis', imageFilterGroups[5][1]],
  ['Conclusions', imageFilterGroups[6][1]],
] as const;

type Bookmark = {
  id: string;
  filter: ImageFilter;
  zoom: number;
  brightness: number;
  contrast: number;
  saturation: number;
  quality: number;
  coefficient?: number;
  shadowLines?: ShadowLine[];
  assessment?: 'Unreviewed'|'Consistent'|'Review required'|'Inconclusive';
  note: string;
};

const formats = /\.(jpe?g|png|webp)$/i;
const modes = [
  {id:'image',label:'Photo'},
  {id:'video',label:'Video'},
  {id:'voice',label:'Voice'},
] as const;
type Mode = typeof modes[number]['id'];
type QueuedFile = {file: File; mode: Mode | null; issue?: string};

const mediaExtensions = {
  image: /\.(jpe?g|jfif|png|webp|heic|heif|gif|avif|bmp|tiff?|svg|ico|dng|raw)$/i,
  video: /\.(mp4|webm|m4v|mov|ogv|avi|mkv|mpg|mpeg|wmv|flv|ts|m2ts|3gp)$/i,
  voice: /\.(wav|mp3|m4a|aac|flac|ogg|oga|opus|aiff?|wma|amr|caf|m4b)$/i,
};
const supportedImage = /\.(jpe?g|jfif|png|webp|heic|heif)$/i;
const supportedImageMime = /^image\/(jpeg|png|webp|heic|heif)(-sequence)?$/i;
const scanLimits = {image:15, voice:25} as const;

function categorize(file: File): QueuedFile {
  const type = file.type.toLowerCase();
  const mode = type.startsWith('image/') ? 'image' :
    type.startsWith('video/') ? 'video' :
    type.startsWith('audio/') ? 'voice' :
    modes.find(item=>mediaExtensions[item.id].test(file.name))?.id ?? null;
  if (!mode) return {file,mode,issue:'Media type could not be identified.'};
  if (!file.size) return {file,mode,issue:'This file is empty.'};
  if (mode==='image' && !(supportedImage.test(file.name) || supportedImageMime.test(type))) {
    return {file,mode,issue:'Image scanning supports static JPEG, PNG, WebP, and HEIC/HEIF when a decoder is available.'};
  }
  if (mode!=='video' && file.size > scanLimits[mode]*1024*1024) {
    return {file,mode,issue:'Exceeds the '+scanLimits[mode]+' MiB scan limit.'};
  }
  return {file,mode};
}

export function DetectionLab({baseUrl,embedded=false}: {baseUrl: string; embedded?: boolean}) {
  const picker = useRef<HTMLInputElement>(null);
  const referencePicker = useRef<HTMLInputElement>(null);
  const [referenceFile,setReferenceFile] = useState<File|null>(null);
  const [referenceUrl,setReferenceUrl] = useState('');
  const [referenceError,setReferenceError] = useState('');
  const [referenceInspection,setReferenceInspection] = useState<InspectionResult>();
  const [imageView,setImageView] = useState<'analysis'|'original'|'compare'>('analysis');
  const [coefficient,setCoefficient] = useState(1);
  const [shadowLines,setShadowLines] = useState<ShadowLine[]>([]);
  const [mode,setMode] = useState<Mode>('image');
  const [videoFile,setVideoFile] = useState<File|null>(null);
  const [videoVersion,setVideoVersion] = useState(0);
  const [voiceFile,setVoiceFile] = useState<File|null>(null);
  const [voiceVersion,setVoiceVersion] = useState(0);
  const [queue,setQueue] = useState<QueuedFile[]>([]);

  function openEvidence(entry: QueuedFile) {
    if (entry.issue || !entry.mode) return;
    setMode(entry.mode);
    if (entry.mode==='voice') {
      if (entry.file===voiceFile) return;
      setVoiceFile(entry.file);
      setVoiceVersion(version=>version+1);
    } else if (entry.mode==='video') {
      if (entry.file===videoFile) return;
      setVideoFile(entry.file);
      setVideoVersion(version=>version+1);
    } else if (entry.file!==file) choose(entry.file);
  }

  function addEvidence(files: FileList) {
    const added = Array.from(files,categorize);
    if (!added.length) return;
    setQueue(previous=>[...previous,...added]);
    const first = added.find(entry=>!entry.issue);
    if (first && !busy) openEvidence(first);
  }

  const [filter,setFilter] = useState<ImageFilter>('visual');
  const imageRef = useRef<HTMLImageElement>(null);
  const [saturation,setSaturation] = useState(100);
  const [quality,setQuality] = useState(90);
  const [inspection,setInspection] = useState<InspectionResult>();
  const [bookmarks,setBookmarks] = useState<Bookmark[]>([]);
  const [bookmarkKey,setBookmarkKey] = useState('');
  const [selectedBookmark,setSelectedBookmark] = useState('');
  const [note,setNote] = useState('');
  const [assessment,setAssessment] = useState<NonNullable<Bookmark['assessment']>>('Unreviewed');
  const [bookmarkStatus,setBookmarkStatus] = useState('');
  const [zoom,setZoom] = useState(100);
  const [brightness,setBrightness] = useState(100);
  const [contrast,setContrast] = useState(100);
  const [dimensions,setDimensions] = useState('');
  const [file,setFile] = useState<File|null>(null);
  const [preview,setPreview] = useState('');
  const [scan,setScan] = useState<DetectionScan|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');

  useEffect(()=>{
    if (!file) {setPreview('');return}
    const url = URL.createObjectURL(file);
    setPreview(url);
    return ()=>URL.revokeObjectURL(url);
  },[file]);

  useEffect(()=>{
    if (!referenceFile) {setReferenceUrl('');return;}
    const url = URL.createObjectURL(referenceFile);
    setReferenceUrl(url);
    return ()=>URL.revokeObjectURL(url);
  },[referenceFile]);

  function chooseReference(next: File) {
    if (!formats.test(next.name) || !next.size || next.size > 15*1024*1024) {
      setReferenceError('Choose a non-empty JPEG, PNG, or WebP reference up to 15 MiB.');
      return;
    }
    setReferenceFile(next);
    setReferenceError('');
    setReferenceInspection(undefined);
    setImageView('compare');
  }

  useEffect(()=>{
    setReferenceInspection(undefined);
    if (!referenceFile || mode!=='image' || ['model','shadows'].includes(filter)) return;
    let current = true;
    const decoded = new window.Image();
    decoded.src = referenceUrl;
    (async()=>{
      await decoded.decode();
      const bytes = new Uint8Array(await referenceFile.arrayBuffer());
      const result = filter==='file' ? fileInformation(referenceFile,bytes,decoded.naturalWidth,decoded.naturalHeight) :
        inspectBytes(filter,bytes) ?? await inspectPixels(filter,decoded,quality,coefficient);
      if (current) setReferenceInspection(result ?? {detail:'Original reference preview.'});
    })().catch(()=>{if(current)setReferenceInspection({detail:'The reference image could not be decoded.'});});
    return ()=>{current=false;};
  },[referenceFile,referenceUrl,filter,quality,coefficient,mode]);

  useEffect(()=>{
    if (!file) return;
    let current = true;
    file.arrayBuffer().then(bytes=>crypto.subtle.digest('SHA-256',bytes)).then(digest=>{
      if (!current) return;
      const key = 'pratyaksh:image-bookmarks:' + Array.from(new Uint8Array(digest),value=>value.toString(16).padStart(2,'0')).join('');
      setBookmarkKey(key);
      try { setBookmarks(JSON.parse(localStorage.getItem(key) ?? '[]')); }
      catch { setBookmarkStatus('Stored bookmarks could not be loaded.'); }
    }).catch(()=>{ if (current) setBookmarkStatus('The file hash could not be computed.'); });
    return ()=>{ current = false; };
  },[file]);

  useEffect(()=>{
    setInspection(undefined);
    if (!file || mode!=='image' || ['visual','model','shadows'].includes(filter)) return;
    let current = true;
    const image = imageRef.current;
    file.arrayBuffer().then(async bytes=>{
      if (filter==='file' && image?.naturalWidth) return fileInformation(file,new Uint8Array(bytes),image.naturalWidth,image.naturalHeight);
      const result = inspectBytes(filter,new Uint8Array(bytes));
      if (result || !image?.naturalWidth) return result;
      return inspectPixels(filter,image,quality,coefficient);
    }).then(result=>{ if (current) setInspection(result); })
      .catch(()=>{ if (current) setInspection({detail:'This filter could not read the image data.'}); });
    return ()=>{ current = false; };
  },[file,filter,dimensions,quality,coefficient,mode]);

  function storeBookmarks(next: Bookmark[]) {
    try {
      localStorage.setItem(bookmarkKey,JSON.stringify(next));
      setBookmarks(next);
      return true;
    } catch {
      setBookmarkStatus('Could not save bookmarks in this browser.');
      return false;
    }
  }

  function saveBookmark() {
    const id = selectedBookmark || crypto.randomUUID();
    const bookmark = {id,filter,zoom,brightness,contrast,saturation,quality,coefficient,shadowLines,assessment,note:note.trim()};
    const next = selectedBookmark ? bookmarks.map(item=>item.id===id?bookmark:item) : [...bookmarks,bookmark];
    if (storeBookmarks(next)) {
      setSelectedBookmark(id);
      setBookmarkStatus('Bookmark saved.');
    }
  }

  function restoreBookmark(bookmark: Bookmark) {
    setSelectedBookmark(bookmark.id);
    setFilter(bookmark.filter);
    setZoom(bookmark.zoom);
    setBrightness(bookmark.brightness);
    setContrast(bookmark.contrast);
    setSaturation(bookmark.saturation);
    setQuality(bookmark.quality);
    setCoefficient(bookmark.coefficient??1);
    setShadowLines(bookmark.shadowLines??[]);
    setImageView('analysis');
    setNote(bookmark.note);
    setAssessment(bookmark.assessment??'Unreviewed');
    setBookmarkStatus('Bookmark restored.');
  }

  function clearBookmarkSelection() {
    setSelectedBookmark('');
    setNote('');
    setAssessment('Unreviewed');
    setBookmarkStatus('');
  }

  function choose(next: File) {
    setScan(null);
    setError('');
    setFile(null);
    setDimensions('');
    setInspection(undefined);
    setFilter('visual');
    setImageView('analysis');
    setCoefficient(1);
    setShadowLines([]);
    setQuality(90);
    setBookmarkKey('');
    setBookmarks([]);
    clearBookmarkSelection();
    resetView();
    setFile(next);
  }

  function resetView() {
    setBrightness(100);
    setContrast(100);
    setSaturation(100);
    setZoom(100);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode!=='image' || !baseUrl || !file || busy) return;
    setFilter('model');
    setBusy(true);
    setError('');
    setScan(null);
    try {
      setScan(await scanLocalFile(baseUrl,file,'image'));
    } catch (error) {
      setError(error instanceof Error ? error.message : 'The scan could not be completed.');
    } finally {
      setBusy(false);
    }
  }

  const results = scan?.findings.filter(finding=>filter==='visual'||(filter==='model')===(finding.category==='synthetic_media'))||[];
  const panelTitle = translate(filterLabels[filter]);
  const currentFile = mode==='voice' ? voiceFile : mode==='video' ? videoFile : file;
  const queueGroups = [...modes, {id:null,label:'Unrecognized'}].map(group=>({
    ...group, entries:queue.filter(entry=>entry.mode===group.id),
  }));
  const localFilter = !['visual','model','shadows'].includes(filter);
  const analysisOutput = imageView!=='original' && localFilter && Boolean(inspection);
  const showFaces = imageView!=='original' && filter==='model' && Boolean(scan?.face_analysis);
  const comparing = imageView==='compare' && Boolean(referenceFile) && !['model','shadows'].includes(filter);

  return <form className="detection-lab" onSubmit={submit} aria-busy={busy}>
    {!embedded && <div className="detection-title">
      <h1>{translate("Deepfake & Synthetic Media Detection")}</h1>
      <span>PRATYAKSH</span>
    </div>}
    <div className="detection-mode" aria-label={translate("Evidence mode")}>
      {modes.map(item=><button key={item.id} type="button" aria-pressed={mode===item.id}
        onClick={()=>setMode(item.id)}>{translate(item.label)}</button>)}
    </div>
    <div className="detection-toolbar">
      <input ref={picker} type="file" hidden multiple
        onChange={event=>{if(event.target.files)addEvidence(event.target.files);event.target.value='';}}/>
      <button className="button secondary" type="button" onClick={()=>picker.current?.click()}>
        <FolderOpen size={16}/>{translate("Add files")}
      </button>
      <div className="detection-path"><span>{translate("Evidence file")}</span><strong>{currentFile?.name||translate('No file selected')}</strong></div>
      {mode==='image' && <button className="button secondary" type="button" disabled={!scan} onClick={()=>{if(scan)download(scan.run_id+'.json',JSON.stringify(scan,null,2))}}>
        <Download size={15}/>{translate("Export scan JSON")}
      </button>}
    </div>
    {queue.length > 0 && <section className="detection-queue" aria-label={translate("Uploaded files")}>
      <div className="detection-queue-header">
        <strong role="status">{queue.length} {translate(queue.length===1?'file':'files')} {translate("added")}</strong>
        <button className="button secondary" type="button" onClick={()=>setQueue([])}>{translate("Clear list")}</button>
      </div>
      <div className="detection-queue-groups">
        {queueGroups.map(group=>group.entries.length > 0 && <details key={group.label} open>
          <summary>{group.label} ({group.entries.length})</summary>
          <ul>{group.entries.map((entry,index)=><li key={index}>
            {entry.issue ? <><strong>{entry.file.name}</strong><small>{entry.issue}</small></> :
              <button type="button" aria-pressed={entry.file===currentFile} disabled={busy}
                onClick={()=>openEvidence(entry)}>{entry.file.name}</button>}
          </li>)}</ul>
        </details>)}
      </div>
    </section>}
    {mode==='image' && <div className="detection-reference-toolbar">
      <input ref={referencePicker} type="file" hidden accept=".jpg,.jpeg,.png,.webp"
        onChange={event=>{const next=event.target.files?.[0];if(next)chooseReference(next);event.target.value='';}}/>
      <button className="button secondary" type="button" onClick={()=>referencePicker.current?.click()}><FolderOpen size={15}/>{translate("Open reference")}</button>
      <div className="detection-path"><span>{translate("Reference image")}</span><strong>{referenceFile?.name||translate('No reference selected')}</strong></div>
      {referenceFile && <button type="button" className="button secondary" onClick={()=>{setReferenceFile(null);setImageView('analysis');setReferenceError('');}}>{translate("Clear reference")}</button>}
      {referenceError && <p role="alert">{referenceError}</p>}
    </div>}
    {(mode==='voice'||voiceFile) && <div hidden={mode!=='voice'}><VoiceInspection key={voiceVersion} file={voiceFile} active={mode==='voice'} baseUrl={baseUrl}/></div>}
    {(mode==='video'||videoFile) && <div hidden={mode!=='video'}><VideoInspection key={videoVersion} file={videoFile} active={mode==='video'} baseUrl={baseUrl}/></div>}
    {mode==='image' && <div className="detection-desktop">
      <aside className="detection-rail">
        <h2 className="detection-pane-title">{translate("Filters")}</h2>
        <div className="detection-filter-tree" aria-label={translate("Inspection filters")}>
          {imageFilterGroups.map(([group, filters])=><details key={group} open>
            <summary>{translate(group)}</summary>
            {filters.map(([id,label])=><button key={id} type="button" aria-pressed={filter===id}
              onClick={()=>{setFilter(id);if(imageView==='original')setImageView('analysis');clearBookmarkSelection();}}>{translate(label)}</button>)}
          </details>)}
        </div>
        <h2 className="detection-pane-title">{translate("Project bookmarks")}</h2>
        <div className="detection-project">
          {file?<><strong>{file.name}</strong><p>{scan?scan.run_id:'No scan recorded'}</p></>:<p>{translate("No evidence loaded")}</p>}
          {file && <>
            <div className="detection-bookmark-actions">
              <button type="button" className="button secondary" onClick={saveBookmark} disabled={!bookmarkKey}>{selectedBookmark?'Update bookmark':'Save bookmark'}</button>
              {selectedBookmark && <>
                <button type="button" className="button secondary" onClick={clearBookmarkSelection}>{translate("New")}</button>
                <button type="button" className="button secondary" onClick={()=>{
                  if (storeBookmarks(bookmarks.filter(item=>item.id!==selectedBookmark))) {
                    clearBookmarkSelection();
                    setBookmarkStatus('Bookmark deleted.');
                  }
                }}>{translate("Delete")}</button>
              </>}
            </div>
            <div className="detection-bookmark-list">
              {bookmarkGroups.map(([group,filters])=>{
                const entries = bookmarks.filter(item=>filters.some(([id])=>id===item.filter));
                return entries.length > 0 && <details open key={group}>
                  <summary>{translate(group)}</summary>
                  {entries.map(item=><button type="button" key={item.id} aria-pressed={selectedBookmark===item.id}
                    onClick={()=>restoreBookmark(item)}><span className={'inspection-bookmark-marker '+(item.assessment||'Unreviewed').toLowerCase().replace(' ','-')} aria-label={translate(item.assessment||'Unreviewed')}/>{translate(filterLabels[item.filter])}{item.note && <small>{item.note}</small>}</button>)}
                </details>;
              })}
            </div>
            <label className="detection-note">{translate("Analyst assessment")}
              <select value={assessment} onChange={event=>setAssessment(event.target.value as typeof assessment)}>
                {['Unreviewed','Consistent','Review required','Inconclusive'].map(value=><option key={value} value={value}>{translate(value)}</option>)}
              </select>
            </label>
            <label className="detection-note">{translate("Bookmark note")}
              <textarea rows={3} maxLength={1000} value={note} onChange={event=>setNote(event.target.value)}/>
            </label>
            {bookmarkStatus && <p role="status">{bookmarkStatus}</p>}
          </>}
        </div>
      </aside>

      <section className="detection-center" aria-label={translate("Evidence viewer")}>
        <h2 className="detection-pane-title">{translate("Evidence viewer")}</h2>
        <div className="detection-view-tools">
          <label className="inspection-view-select">{translate("View")}
            <select aria-label={translate("Image view")} value={imageView} onChange={event=>setImageView(event.target.value as typeof imageView)}>
              <option value="analysis">{translate("Analysis")}</option><option value="original">{translate("Original")}</option>
              <option value="compare" disabled={!referenceFile||['model','shadows'].includes(filter)}>{translate("Evidence / Reference")}</option>
            </select>
          </label>
          <div>
            <button type="button" aria-label={translate("Zoom out")} disabled={!preview} onClick={()=>setZoom(Math.max(25,zoom-25))}><Minus size={15}/></button>
            <output>{zoom}%</output>
            <button type="button" aria-label={translate("Zoom in")} disabled={!preview} onClick={()=>setZoom(Math.min(300,zoom+25))}><Plus size={15}/></button>
            <button type="button" disabled={!preview} onClick={()=>setZoom(100)}>{translate("Fit")}</button>
          </div>
        </div>
        <div className={'detection-stage image-auth-stage'+(analysisOutput?' inspection-analysis-stage':'')}>
          {file && preview && <img ref={imageRef} hidden={analysisOutput||comparing||filter==='shadows'||showFaces} src={preview} alt={file.name}
            onLoad={event=>setDimensions(event.currentTarget.naturalWidth+' × '+event.currentTarget.naturalHeight+' px')}
            onError={()=>setError('Image preview could not be decoded.')}
            style={{width:zoom+'%',filter:'brightness('+brightness+'%) contrast('+contrast+'%) saturate('+saturation+'%)'}}/>}
          {!file||!preview ? <div className="detection-stage-empty"><Image size={30}/><strong>{translate("No evidence loaded")}</strong><p>{translate("Add files to open an image.")}</p></div> :
            showFaces && scan?.face_analysis ? <FaceAnalysisViewer key={scan.run_id} src={preview} analysis={scan.face_analysis} file={file} baseUrl={baseUrl} sha256={scan.sha256}
              modelVersion={scan.findings.find(finding=>finding.finding_id===scan.face_analysis?.finding_id)?.method_version}/> :
            filter==='shadows' ? <ShadowInspection src={preview} lines={shadowLines} onChange={setShadowLines}/> :
            comparing ? inspection && referenceInspection && localFilter ?
              <InspectionComparison evidence={inspection} reference={referenceInspection}/> :
              <div className="inspection-compare-grid">
                <section><h3>{translate("Evidence")}</h3><img className="inspection-result-image" src={preview} alt={translate("Evidence comparison preview")}/></section>
                <section><h3>{translate("Reference")}</h3><img className="inspection-result-image" src={referenceUrl} alt={translate("Reference comparison preview")}/></section>
              </div> :
            analysisOutput && inspection && <div className="detection-table-scroll inspection-primary-output">
              {inspection.image && <img src={inspection.image} alt={panelTitle+' output'} style={{width:zoom+'%'}}/>}
              <InspectionOutput result={inspection}/>
            </div>}
        </div>
        <div className="detection-adjustments" aria-label={translate("Image adjustments")}>
          {([['Brightness',brightness,setBrightness],['Contrast',contrast,setContrast],['Saturation',saturation,setSaturation]] as const)
            .map(([label,value,update])=><label key={label}>{label}<input type="range" min="0" max="200"
              aria-label={label} value={value} disabled={!dimensions||analysisOutput||comparing||filter==='shadows'} onChange={event=>update(+event.target.value)}/><output>{value}%</output></label>)}
          <button className="button secondary" type="button" disabled={!dimensions} onClick={resetView}>{translate("Reset view")}</button>
        </div>
        <div className="detection-view-status"><span>{file?.type||'Media type unavailable'}</span><span>{dimensions||'—'}</span><span>{file?(file.size/1024).toFixed(1)+' KiB':'—'}</span></div>
        <section className="detection-results-pane" aria-label={translate("Scan results")}>
          <h2 className="detection-pane-title">{translate("Table viewer ·")} {panelTitle}</h2>
          <div className="detection-table-scroll">
            {filter==='shadows' ? <p>{shadowLines.length} {translate("manual shadow lines recorded.")}</p> : localFilter ? inspection ? <p>{inspection.detail||'Results displayed in the center viewer.'}</p> :
              <p role="status">{file?(error||'Reading image…'):'Open an image to use this filter.'}</p> :
              !scan?<p role="status">{busy?'Running detector and file inspection…':'Run a scan to populate the findings table.'}</p>:<>
              <p role="status"><strong>{scan.summary.result==='inconclusive'?'Inconclusive':'Unavailable'}</strong> · {scan.summary.completed_checks}/{scan.summary.total_checks} {translate("checks completed")}</p>
              <table className="detection-scan-table">
                <thead><tr><th>{translate("Check")}</th><th>{translate("Status")}</th><th>{translate("Raw score")}</th><th>{translate("What it means")}</th></tr></thead>
                <tbody>{results.map(finding=><tr key={finding.finding_id}>
                  <td>{finding.method}</td><td><span className={'badge '+tone(finding)}>{classification(finding)}</span></td>
                  <td>{finding.score?.value==null?'—':finding.score.value.toFixed(3)}</td>
                  <td>{scoreMeaning(finding)}<details><summary>{translate("Scope and limitations")}</summary>
                    <p>{finding.observation}</p>
                    <p>{finding.scope}</p>
                    {finding.score&&<p>{finding.score.positive_class} · {finding.score.calibration_status}</p>}
                    {finding.limitations.map(limit=><p key={limit}>{limit}</p>)}
                  </details></td>
                </tr>)}</tbody>
              </table>
              <p>{scan.summary.result==='inconclusive' ? 'The app could not determine whether the file was manipulated. ' : ''}{translate("Scores show what each model picked up and cannot be read as percentages of AI content.")}</p>
              <p>{scan.summary.reason}</p>
            </>}
          </div>
        </section>
      </section>

      <aside className="detection-parameters">
        <h2 className="detection-pane-title">{translate("Filter parameters")}</h2>
        <div className="detection-parameter-body">
          <h3>{panelTitle}</h3>
          {filter==='shadows'&&<>
            <p>{translate("Draw lines on the image and save them with an analyst note using Project bookmarks.")}</p>
            <button type="button" className="button secondary" disabled={!shadowLines.length} onClick={()=>setShadowLines([])}>{translate("Clear lines")}</button>
          </>}
          {filter==='visual'&&<p>{translate("Adjust the decoded preview using the controls below the image.")}</p>}
          {filter==='ela'&&<label className="field">{translate("JPEG quality")} <output>{quality}</output>
            <input type="range" min="50" max="100" value={quality} disabled={!dimensions} onChange={event=>setQuality(+event.target.value)}/>
          </label>}
          {(filter==='dct'||filter==='dctMap')&&<label className="field">{translate("DCT coefficient")}
            <select aria-label={translate("DCT coefficient")} value={coefficient} onChange={event=>setCoefficient(+event.target.value)}>
              <option value={1}>{translate("Horizontal AC (1, 0)")}</option><option value={2}>{translate("Horizontal AC (2, 0)")}</option>
              <option value={8}>{translate("Vertical AC (0, 1)")}</option><option value={24}>{translate("Vertical AC (0, 3)")}</option>
            </select>
          </label>}
          {filter==='file'&&<dl className="detection-file-info">
            <dt>{translate("Filename")}</dt><dd>{file?.name||'—'}</dd>
            <dt>{translate("Dimensions")}</dt><dd>{dimensions||'—'}</dd>
            <dt>SHA-256</dt><dd className="mono">{scan?.sha256||bookmarkKey.split(':').at(-1)||'Pending'}</dd>
          </dl>}
          {filter==='model'&&<dl className="detection-file-info"><dt>{translate("Model")}</dt><dd>{!file?'Select evidence':'UniversalFakeDetect + SBI'}</dd><dt>{translate("Scope")}</dt><dd>{!file?'—':'AI-generation signal and detected face crops'}</dd></dl>}
          {!baseUrl&&<p className="notice">{translate("Set VITE_D1_API_BASE_URL to connect the detection backend.")}</p>}
          {error&&<p className="notice" role="alert">{error}</p>}
          <button className="button primary full" type="submit" disabled={!file||!baseUrl||busy}>
            {busy?<Loader2 className="spin" size={16}/>:<ScanSearch size={16}/>}
            {translate(busy?'Running checks…':'Run deepfake scan')}
          </button>
        </div>
      </aside>
    </div>}
  </form>;
}
