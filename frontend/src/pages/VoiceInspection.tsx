import {translate,useFormatters} from '../i18n';
import {scoreMeaning} from '../data/scoreMeaning';
import {useEffect, useRef, useState, type MouseEvent} from 'react';
import {AudioLines, Download, Loader2, ScanSearch} from 'lucide-react';
import {scanLocalFile, type DetectionScan} from '../data/detectionScan';
import {classification, download, tone} from '../model';

const filters = [
  ['Overview', ['Waveform', 'File Information']],
  ['Deepfake Detection', ['Synthetic Speech Scan']],
] as const;
type Filter = typeof filters[number][1][number];
type Waveform = {peaks: number[]; channels: number; decodedRate: number};
type Bookmark = {id: string; seconds: number; note: string};


function timecode(seconds: number) {
  return Math.floor(seconds/60) + ':' + String(Math.floor(seconds)%60).padStart(2,'0');
}

function measureWaveform(buffer: AudioBuffer): Waveform {
  const bins = 240;
  const peaks = Array<number>(bins).fill(0);
  for (let channel=0; channel<buffer.numberOfChannels; channel++) {
    const values = buffer.getChannelData(channel);
    for (let i=0; i<bins; i++) {
      const start = Math.floor(i*values.length/bins);
      const end = Math.floor((i+1)*values.length/bins);
      for (let at=start; at<end; at++) peaks[i] = Math.max(peaks[i],Math.abs(values[at]));
    }
  }
  return {peaks,channels:buffer.numberOfChannels,decodedRate:buffer.sampleRate};
}

export function VoiceInspection({file, active, baseUrl}: {file: File|null; active: boolean; baseUrl: string}) {
  const {formatNumber}=useFormatters();
  const player = useRef<HTMLAudioElement>(null);
  const [url,setUrl] = useState('');
  const [filter,setFilter] = useState<Filter>('Waveform');
  const [waveform,setWaveform] = useState<Waveform>();
  const [waveformStatus,setWaveformStatus] = useState('');
  const [playbackError,setPlaybackError] = useState('');
  const [duration,setDuration] = useState(0);
  const [time,setTime] = useState(0);
  const [rate,setRate] = useState(1);
  const [normalize,setNormalize] = useState(false);
  const [note,setNote] = useState('');
  const [bookmarks,setBookmarks] = useState<Bookmark[]>([]);
  const [busy,setBusy] = useState(false);
  const [scan,setScan] = useState<DetectionScan|null>(null);
  const [scanError,setScanError] = useState('');

  useEffect(()=>{
    if (!file) return;
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    setWaveformStatus('Decoding waveform…');
    let current = true;
    let context: AudioContext | undefined;
    file.arrayBuffer().then(async bytes=>{
      if (!current) return;
      context = new AudioContext();
      const decoded = await context.decodeAudioData(bytes);
      if (current) {
        setWaveform(measureWaveform(decoded));
        setWaveformStatus('');
      }
    }).catch(()=>{
      if (current) setWaveformStatus('Waveform unavailable for this file.');
    }).finally(()=>{
      if (context) void context.close().catch(()=>{});
    });
    return ()=>{current = false; URL.revokeObjectURL(objectUrl);};
  },[file]);

  useEffect(()=>{ if (!active) player.current?.pause(); },[active]);
  useEffect(()=>{ if (player.current) player.current.playbackRate = rate; },[rate,url]);

  function seek(seconds: number) {
    if (player.current && duration > 0) player.current.currentTime = Math.min(duration,Math.max(0,seconds));
  }

  function seekOnWaveform(event: MouseEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    seek((event.clientX-bounds.left)/bounds.width*duration);
  }

  async function runScan() {
    if (!baseUrl || !file || busy) return;
    setFilter('Synthetic Speech Scan');
    setBusy(true);
    setScan(null);
    setScanError('');
    try {
      setScan(await scanLocalFile(baseUrl,file,'audio'));
    } catch (error) {
      setScanError(error instanceof Error ? error.message : 'The scan could not be completed.');
    } finally {
      setBusy(false);
    }
  }

  const max = normalize && waveform ? Math.max(.00001,...waveform.peaks) : 1;
  const position = duration ? time/duration*720 : 0;
  const rows = [
    ['Voice file',file?.name||'—'],
    ['Reported media type',file?.type||'—'],
    ['Duration',duration ? timecode(duration) : '—'],
    ['Decoded channels',waveform?.channels ?? '—'],
    ['Waveform sample rate',waveform ? formatNumber(waveform.decodedRate)+' Hz (browser decoded)' : '—'],
    ['File size',file ? formatNumber(file.size)+' bytes' : '—'],
  ];

  return <div className="detection-desktop video-inspection voice-inspection">
    <aside className="detection-rail">
      <h2 className="detection-pane-title">{translate("Filters")}</h2>
      <div className="detection-filter-tree" aria-label={translate("Voice filters")}>
        {filters.map(([group,items])=><details open key={group}>
          <summary>{translate(group)}</summary>
          {items.map(item=><button key={item} type="button" aria-pressed={filter===item} onClick={()=>setFilter(item)}>{translate(item)}</button>)}
        </details>)}
      </div>
      <h2 className="detection-pane-title">{translate("Project bookmarks")}</h2>
      <div className="detection-project">
        {file ? <>
          <div className="detection-bookmark-list">
            {bookmarks.map(bookmark=><div key={bookmark.id} className="video-bookmark">
              <button type="button" onClick={()=>seek(bookmark.seconds)}>{timecode(bookmark.seconds)} · {bookmark.note}</button>
              <button type="button" aria-label={'Delete '+bookmark.note} onClick={()=>setBookmarks(items=>items.filter(item=>item.id!==bookmark.id))}>×</button>
            </div>)}
          </div>
          <label className="detection-note">{translate("Bookmark note")}
            <textarea rows={2} maxLength={200} value={note} onChange={event=>setNote(event.target.value)}/>
          </label>
          <div className="detection-bookmark-actions">
            <button type="button" className="button secondary" disabled={!duration} onClick={()=>{
              setBookmarks(items=>[...items,{id:crypto.randomUUID(),seconds:player.current?.currentTime??time,note:note.trim()||'Voice review'}]);
              setNote('');
            }}>{translate("Save bookmark")}</button>
          </div>
          <p>{translate("Bookmarks are kept while this clip is open.")}</p>
        </> : <p>{translate("No voice clip loaded")}</p>}
      </div>
    </aside>

    <section className="detection-center" aria-label={translate("Voice player")}>
      <h2 className="detection-pane-title">{translate("Player / Waveform")}</h2>
      <div className="voice-stage">
        {!file ? <div className="detection-stage-empty"><AudioLines size={30}/><strong>{translate("No voice clip loaded")}</strong><p>{translate("Open a WAV or MP3 up to 25 MiB.")}</p></div> : <>
          {waveform ? <svg viewBox="0 0 720 148" preserveAspectRatio="none" role="img" aria-label={translate("Audio peak waveform")} onClick={seekOnWaveform}>
            <path className="voice-axis" d="M0 74H720"/>
            <path className="voice-peaks" d={waveform.peaks.map((peak,i)=>{
              const x = i*3+1.5;
              const height = Math.min(1,peak/max)*68;
              return 'M'+x+' '+(74-height)+'V'+(74+height);
            }).join(' ')}/>
            <path className="voice-position" d={'M'+position+' 0V148'}/>
          </svg> : <p role="status">{waveformStatus}</p>}
          <audio ref={player} controls preload="metadata" src={url||undefined} aria-label={translate("Evidence voice clip")}
            onLoadedMetadata={event=>setDuration(Number.isFinite(event.currentTarget.duration)?event.currentTarget.duration:0)}
            onTimeUpdate={event=>setTime(event.currentTarget.currentTime)}
            onError={()=>setPlaybackError('This voice clip could not be played by the browser.')}/>
          <div className="voice-time"><span>{timecode(time)}</span><span>{timecode(duration)}</span></div>
          {playbackError && <p role="alert">{playbackError}</p>}
        </>}
      </div>

      <section className="detection-table-scroll" aria-label={translate("Voice file details")}>
        <h2 className="detection-pane-title">{translate("Table Viewer · File Information")}</h2>
        <table><tbody>{rows.map(([label,value])=><tr key={label}><th scope="row">{label}</th><td>{value}</td></tr>)}</tbody></table>
      </section>
      {(filter==='Synthetic Speech Scan'||scan) && <section className="detection-table-scroll" aria-label={translate("Voice scan results")}>
        <h2 className="detection-pane-title">{translate("Synthetic Speech Findings")}</h2>
        {busy ? <p role="status">{translate("Running the audio detector and file inspection…")}</p> : scan ? <>
          <p role="status"><strong>{scan.summary.result==='inconclusive'?'Inconclusive':'Unavailable'}</strong> · {scan.summary.completed_checks}/{scan.summary.total_checks} {translate("checks completed")}</p>
          <table className="detection-scan-table"><thead><tr><th>{translate("Check")}</th><th>{translate("Status")}</th><th>{translate("Raw score")}</th><th>{translate("What it means")}</th></tr></thead>
            <tbody>{scan.findings.map(finding=><tr key={finding.finding_id}>
              <th scope="row">{finding.method}</th>
              <td><span className={'badge '+tone(finding)}>{classification(finding)}</span></td>
              <td>{finding.score?.value?.toFixed(3)??'—'}</td>
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
        </> : <p>{translate("Run a voice scan to populate the findings table.")}</p>}
      </section>}
    </section>

    <aside className="detection-parameters">
      <h2 className="detection-pane-title">{translate("Filter Parameters ·")} {translate(filter)}</h2>
      <div className="detection-parameter-body">
        {filter==='Waveform' && <>
          <label className="field">{translate("Playback speed")}
            <select value={rate} disabled={!duration} onChange={event=>setRate(Number(event.target.value))}>
              {[.5,.75,1,1.25,1.5,2].map(value=><option value={value} key={value}>{value}×</option>)}
            </select>
          </label>
          <label className="voice-toggle"><input type="checkbox" checked={normalize} disabled={!waveform} onChange={event=>setNormalize(event.target.checked)}/>{translate("Normalize waveform display")}</label>
          <button className="button secondary" type="button" disabled={!duration} onClick={()=>{setRate(1);setNormalize(false);}}>{translate("Reset preview")}</button>
        </>}
        {filter==='File Information' && <dl className="detection-file-info">
          <dt>SHA-256</dt><dd className="mono">{scan?.sha256||'Available after scan'}</dd>
        </dl>}
        {filter==='Synthetic Speech Scan' && <dl className="detection-file-info">
          <dt>{translate("Model")}</dt><dd>AASIST</dd><dt>{translate("Scope")}</dt><dd>{translate("Opening audio segment")}</dd>
        </dl>}
        {!baseUrl && <p className="notice">{translate("Set VITE_D1_API_BASE_URL to connect the detection backend.")}</p>}
        {scanError && <p className="notice" role="alert">{scanError}</p>}
        <button className="button primary full" type="button" disabled={!file||!baseUrl||busy} onClick={runScan}>
          {busy?<Loader2 className="spin" size={16}/>:<ScanSearch size={16}/>}
          {translate(busy?'Running checks…':'Run voice scan')}
        </button>
        {scan && <button className="button secondary full" type="button" onClick={()=>download(scan.run_id+'.json',JSON.stringify(scan,null,2))}>
          <Download size={15}/>{translate("Export scan JSON")}
        </button>}
      </div>
    </aside>
  </div>;
}
