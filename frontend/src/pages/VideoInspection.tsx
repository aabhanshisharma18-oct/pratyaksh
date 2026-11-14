import {translate,useFormatters} from '../i18n';
import {useEffect, useId, useRef, useState} from 'react';
import {FolderOpen,ScanSearch} from 'lucide-react';
import {scanLocalVideo,type VideoDetectionScan} from '../data/detectionScan';
import {videoFrameScoreMeaning} from '../data/scoreMeaning';

const videoFilters = [
  ['Overview', ['Visual Inspection']],
  ['File Analysis', ['Advanced File Info']],
  ['Camera Identification', ['Create PRNU CRP', 'PRNU Source Identification']],
  ['Compression Analysis', ['VPF', 'Macroblocks', 'Motion Vectors']],
  ['Continuity Analysis', ['Channels', 'Block Difference', 'PRNU Tampering']],
] as const;

type VideoFilter = typeof videoFilters[number][1][number];
const channels = ['RGB', 'Red', 'Green', 'Blue', 'Luma'] as const;
type Channel = typeof channels[number];
type View = {shadows: number; midtones: number; highlights: number; channel: Channel};
type Sample = {time: number; rgb: [number, number, number]};
type Bookmark = {id: string; name: string; time: number; filter: VideoFilter; view: View};
const defaultView: View = {shadows:0, midtones:128, highlights:255, channel:'RGB'};
const colors = ['#b84b56', '#398064', '#477bc0'];
const channelWeights = {Red:[1,0,0], Green:[0,1,0], Blue:[0,0,1], Luma:[.2126,.7152,.0722]};


function timecode(seconds: number) {
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  return minutes + ':' + String(whole % 60).padStart(2,'0');
}

export function VideoInspection({file,active,baseUrl}: {file: File | null; active: boolean; baseUrl: string}) {
  const {formatNumber}=useFormatters();
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const filterId = useId();
  const [url,setUrl] = useState('');
  const [filter,setFilter] = useState<VideoFilter>('Visual Inspection');
  const [view,setView] = useState(defaultView);
  const [applied,setApplied] = useState(defaultView);
  const [info,setInfo] = useState({width:0,height:0,duration:0});
  const [time,setTime] = useState(0);
  const [samples,setSamples] = useState<Sample[]>([]);
  const [bookmarks,setBookmarks] = useState<Bookmark[]>([]);
  const [note,setNote] = useState('');
  const [error,setError] = useState('');

  const scanController = useRef<AbortController|null>(null);
  const [scan,setScan] = useState<VideoDetectionScan|null>(null);
  const [scanError,setScanError] = useState('');
  const [scanning,setScanning] = useState(false);

  useEffect(()=>()=>scanController.current?.abort(),[]);

  async function runVideoScan() {
    if (!file || !baseUrl || scanController.current) return;
    const controller = new AbortController();
    scanController.current = controller;
    setScanning(true);
    setScanError('');
    setScan(null);
    try {
      const result = await scanLocalVideo(baseUrl,file,controller.signal);
      if (!controller.signal.aborted) setScan(result);
    } catch (error) {
      if (!controller.signal.aborted) setScanError(error instanceof Error?error.message:'The video scan failed.');
    } finally {
      if (!controller.signal.aborted) setScanning(false);
      scanController.current = null;
    }
  }

  useEffect(()=>{
    if (!file) return;
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return ()=>URL.revokeObjectURL(objectUrl);
  },[file]);

  useEffect(()=>{ if (!active) video.current?.pause(); },[active]);

  function recordFrame() {
    const source = video.current;
    if (!source || source.readyState < 2) return;
    setTime(source.currentTime);
    const context = canvas.current?.getContext('2d',{willReadFrequently:true});
    if (!context) return;
    context.drawImage(source,0,0,48,27);
    const pixels = context.getImageData(0,0,48,27).data;
    const rgb: Sample['rgb'] = [0,0,0];
    for (let at = 0; at < pixels.length; at += 4) {
      rgb[0] += pixels[at];
      rgb[1] += pixels[at + 1];
      rgb[2] += pixels[at + 2];
    }
    for (let i = 0; i < rgb.length; i++) rgb[i] /= pixels.length / 4;
    const bucket = Math.floor(source.currentTime * 2) / 2;
    setSamples(previous=>[...previous.filter(sample=>sample.time!==bucket), {time:bucket,rgb}]
      .slice(-480).sort((a,b)=>a.time-b.time));
  }

  function seek(seconds: number) {
    if (video.current && info.duration > 0) video.current.currentTime = Math.min(info.duration,Math.max(0,seconds));
  }

  const levels = [view.shadows / 255, view.midtones===128 ? .5 : view.midtones / 255, view.highlights / 255].join(' ');
  const weights = view.channel==='RGB' ? null : channelWeights[view.channel].join(' ') + ' 0 0';
  const x = (seconds: number) => 14 + 472 * seconds / (info.duration || 1);
  const ready = Boolean(info.width) && !error;
  const rows = [
    ['Video file',file?.name||'—'],
    ['Reported media type',file?.type||'—'],
    ['Input resolution',info.width ? info.width + ' × ' + info.height : '—'],
    ['Duration',info.duration ? timecode(info.duration) : '—'],
    ['Current position',ready ? time.toFixed(2) + ' s' : '—'],
    ['File size',file ? formatNumber(file.size) + ' bytes' : '—'],
  ];

  return <div className="detection-desktop video-inspection">
    <aside className="detection-rail">
      <h2 className="detection-pane-title">{translate("Filters")}</h2>
      <div className="detection-filter-tree" aria-label={translate("Video filters")}>
        {videoFilters.map(([group,items])=><details open key={group}>
          <summary>{translate(group)}</summary>
          {items.map(item=><button key={item} type="button" aria-pressed={filter===item} onClick={()=>setFilter(item)}>{translate(item)}</button>)}
        </details>)}
      </div>
      <h2 className="detection-pane-title">{translate("Project bookmarks")}</h2>
      <div className="detection-project">
        <div className="detection-bookmark-list">
          {bookmarks.map(bookmark=><div className="video-bookmark" key={bookmark.id}>
            <button type="button" onClick={()=>{
              setFilter(bookmark.filter); setView(bookmark.view); setApplied(bookmark.view); seek(bookmark.time);
            }}>{timecode(bookmark.time)} · {bookmark.name}</button>
            <button type="button" aria-label={'Delete '+bookmark.name} onClick={()=>setBookmarks(items=>items.filter(item=>item.id!==bookmark.id))}>×</button>
          </div>)}
        </div>
        <label className="detection-note">{translate("Bookmark note")}
          <textarea rows={2} maxLength={200} value={note} disabled={!ready} onChange={event=>setNote(event.target.value)}/>
        </label>
        <div className="detection-bookmark-actions">
          <button type="button" className="button secondary" disabled={!ready} onClick={()=>{
            setBookmarks(items=>[...items,{id:crypto.randomUUID(),name:note.trim()||filter,time:video.current?.currentTime??0,filter,view}]);
            setNote('');
          }}>{translate("Save bookmark")}</button>
        </div>
        <p>{translate("Bookmarks are kept while this clip is open.")}</p>
      </div>
    </aside>

    <section className="detection-center" aria-label={translate("Video player")}>
      <h2 className="detection-pane-title">{translate("Player / Viewer")}</h2>
      <div className="detection-stage video-stage">
        {!file ? <div className="detection-stage-empty"><FolderOpen size={30}/><strong>{translate("No video loaded")}</strong><p>{translate("Open a local video to start playback.")}</p></div> :
          <video ref={video} src={url||undefined} controls playsInline preload="metadata"
            aria-label={translate("Evidence video")} style={{filter:'url(#'+filterId+')'}}
            onLoadedMetadata={event=>{
              const source = event.currentTarget;
              setInfo({width:source.videoWidth,height:source.videoHeight,duration:Number.isFinite(source.duration)?source.duration:0});
              setError('');
            }}
            onLoadedData={recordFrame} onTimeUpdate={recordFrame} onSeeked={recordFrame}
            onError={()=>setError('This video could not be played. Try an MP4 or WebM encoded with a codec supported by your browser.')}/>}
        <canvas ref={canvas} width={48} height={27} hidden/>
        <svg className="video-filter-definition" aria-hidden="true">
          <defs><filter id={filterId} colorInterpolationFilters="sRGB">
            {weights && <feColorMatrix type="matrix" values={weights+' '+weights+' '+weights+' 0 0 0 1 0'}/>}
            <feComponentTransfer>
              <feFuncR type="table" tableValues={levels}/>
              <feFuncG type="table" tableValues={levels}/>
              <feFuncB type="table" tableValues={levels}/>
            </feComponentTransfer>
          </filter></defs>
        </svg>
      </div>
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="detection-view-status"><span>{timecode(time)} / {timecode(info.duration)}</span><span>{rows[2][1]}</span></div>
      <section className="video-scan" aria-label={translate("Video detection results")}>
        <h2 className="detection-pane-title">{translate("Synthetic media scan")}</h2>
        <div className="detection-parameter-body">
          {scanning ? <p role="status">{translate("Sampling and scoring video frames…")}</p> :
            scanError ? <p className="notice" role="alert">{scanError}</p> :
            scan ? <>
              <p role="status"><strong>{translate("Inconclusive")}</strong> · {formatNumber(scan.samples.length)} {translate("of")} {formatNumber(scan.sampling.requested_samples)} {translate("requested frames scored")}</p>
              <p><strong>{translate("Average frame score")} {formatNumber(scan.aggregation.mean_score,{maximumFractionDigits:3})}</strong> · <strong>{translate("Peak frame score")} {formatNumber(scan.aggregation.maximum_score,{maximumFractionDigits:3})}</strong></p>
              <p>{translate(videoFrameScoreMeaning(scan.aggregation.maximum_score))} {translate("This is the strongest signal across the frames checked.")}</p>
              <p>{translate("The model checks for signs of AI-generated imagery in sampled frames. These scores are on a 0–1 scale. A video-level verdict requires a validated cutoff. Audio, lip sync, and frames between samples were outside this scan.")}</p>
              <div className="detection-table-scroll"><table className="detection-scan-table">
                <thead><tr><th scope="col">{translate("Timestamp")}</th><th scope="col">{translate("Model score")}</th><th scope="col">{translate("What it means")}</th></tr></thead>
                <tbody>{scan.samples.map(sample=><tr key={sample.sample_id}>
                  <td>{ready?<button type="button" className="button secondary" onClick={()=>seek(sample.timestamp_ms/1000)}>{formatNumber(sample.timestamp_ms/1000,{maximumFractionDigits:2})} {translate("s")}</button>:
                    formatNumber(sample.timestamp_ms/1000,{maximumFractionDigits:2})+' '+translate("s")}</td>
                  <td>{formatNumber(sample.deepfake_score,{maximumFractionDigits:3})}</td><td>{translate(videoFrameScoreMeaning(sample.deepfake_score))}</td>
                </tr>)}</tbody>
              </table></div>
              {scan.sampling.rejected_samples.length>0 && <p>{formatNumber(scan.sampling.rejected_samples.length)} {translate("samples could not be scored.")}</p>}
              <details><summary>{translate("Model and limitations")}</summary><p>{scan.finding.method} · {scan.finding.method_version}</p>
                <ul>{scan.finding.limitations.map(limit=><li key={limit}>{limit}</li>)}</ul>
              </details>
            </> : <p>{translate("Run a video scan to see frame scores and what they mean.")}</p>}
        </div>
      </section>
      <div className="video-readouts">
        <section aria-label={translate("Plot viewer")}>
          <h2 className="detection-pane-title">{translate("Plot Viewer")}</h2>
          {samples.length ? <div className="inspection-chart">
            <svg viewBox="0 0 500 125" role="img" aria-label={translate("Mean red, green and blue levels over sampled playback")}>
              <path d="M14 8V113H486" fill="none" stroke="currentColor" opacity=".35"/>
              {colors.map((color,index)=><polyline key={color} fill="none" stroke={color} strokeWidth="2"
                points={samples.map(sample=>x(sample.time)+','+(112 - 103 * sample.rgb[index] / 255)).join(' ')}/>)}
              <line x1={x(time)} x2={x(time)} y1="8" y2="113" stroke="currentColor" strokeDasharray="3 3"/>
            </svg>
            <p>{translate("Original-frame mean RGB · Samples collected during playback and seeking")}</p>
          </div> : <p>{translate("Load and play a clip to plot frame color levels.")}</p>}
        </section>
        <section className="detection-table-scroll" aria-label={translate("Table viewer")}>
          <h2 className="detection-pane-title">{translate("Table Viewer")}</h2>
          <table><tbody>{rows.map(([label,value])=><tr key={label}><th scope="row">{label}</th><td>{value}</td></tr>)}</tbody></table>
        </section>
      </div>
    </section>

    <aside className="detection-parameters">
      <h2 className="detection-pane-title">{translate("Filter Parameters ·")} {translate(filter)}</h2>
      <div className="detection-parameter-body">
        {filter==='Visual Inspection' && (['highlights','midtones','shadows'] as const).map(key=>
          <label className="field video-level" key={key}><span>{key}</span><output>{view[key]}</output>
            <input type="range" min="0" max="255" value={view[key]} disabled={!ready}
              aria-label={key[0].toUpperCase()+key.slice(1)}
              onChange={event=>setView(previous=>({...previous,[key]:+event.target.value}))}/>
          </label>)}
        {filter==='Channels' && <label className="field">{translate("Channel")}
          <select value={view.channel} disabled={!ready} onChange={event=>setView(previous=>({...previous,channel:event.target.value as Channel}))}>
            {channels.map(channel=><option key={channel}>{channel}</option>)}
          </select>
        </label>}
        {(filter==='Visual Inspection'||filter==='Channels') && <>
          <div className="video-filter-actions">
            <button className="button secondary" type="button" disabled={!ready||view===applied} onClick={()=>setApplied(view)}>{translate("Apply")}</button>
            <button className="button secondary" type="button" disabled={!ready||view===applied} onClick={()=>setView(applied)}>{translate("Abort")}</button>
            <button className="button secondary" type="button" disabled={!ready} onClick={()=>setView(defaultView)}>{translate("Reset")}</button>
          </div>
          <p>{view===applied?'Playback view settings are applied.':'Previewing adjustments during playback.'}</p>
        </>}
        <button type="button" className="button primary full" onClick={runVideoScan}
          disabled={!file||!baseUrl||scanning||file.size>50*1024*1024}>
          <ScanSearch size={15}/>{translate(scanning?'Scanning video…':'Run video deepfake scan')}
        </button>
        {!baseUrl && <p>{translate("Set VITE_D1_API_BASE_URL to connect the detection backend.")}</p>}
        {file && file.size>50*1024*1024 && <p>{translate("The video scan accepts files up to 50 MiB.")}</p>}
        {filter==='Advanced File Info' && <p>{translate("See the decoded video properties in the Table Viewer.")}</p>}
        {!['Visual Inspection','Channels','Advanced File Info'].includes(filter) && <p>{translate("This analysis filter is unavailable in the current video workspace.")}</p>}
      </div>
    </aside>
  </div>;
}
