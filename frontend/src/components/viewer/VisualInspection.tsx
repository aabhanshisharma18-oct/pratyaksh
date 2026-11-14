import {translate} from '../../i18n';
import {useEffect, useRef, useState} from 'react';
import type {Evidence} from '../../model';
import {formatTimeMs} from '../../viewer/timeFormat';
import './inspection.css';

const channels = ['RGB', 'Red', 'Green', 'Blue'] as const;
const colors = ['#b84f62', '#45806b', '#527daf'];
type Channel = typeof channels[number];

export function VisualInspection({evidence, positionMs}: {evidence: Evidence; positionMs: number}) {
  const original = useRef<ImageData | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [channel, setChannel] = useState<Channel>('RGB');
  const [brightness, setBrightness] = useState(100);
  const [contrast, setContrast] = useState(100);
  const [histogram, setHistogram] = useState<number[][]>([]);
  const [sample, setSample] = useState('');
  const [error, setError] = useState('');

  function capture(source: HTMLImageElement | HTMLVideoElement) {
    const isVideo = source instanceof HTMLVideoElement;
    const width = isVideo ? source.videoWidth : source.naturalWidth;
    const height = isVideo ? source.videoHeight : source.naturalHeight;
    if (!width || !height) return;
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    const scale = Math.min(1, 1024 / Math.max(width, height));
    context.canvas.width = Math.max(1, Math.round(width * scale));
    context.canvas.height = Math.max(1, Math.round(height * scale));
    try {
      context.drawImage(source, 0, 0, context.canvas.width, context.canvas.height);
      const pixels = context.getImageData(0, 0, context.canvas.width, context.canvas.height);
      const bins = Array.from({length: 3}, () => Array<number>(32).fill(0));
      for (let offset = 0; offset < pixels.data.length; offset += 4) {
        if (pixels.data[offset + 3] === 0) continue;
        for (let rgb = 0; rgb < 3; rgb++) bins[rgb][pixels.data[offset + rgb] >> 3]++;
      }
      original.current = pixels;
      setHistogram(bins);
      setSample(isVideo ? `Frame at ${formatTimeMs(Math.round(source.currentTime * 1000))}` : 'Decoded image');
      setError('');
    } catch {
      setError('This media could not be sampled for pixel inspection.');
    }
  }

  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    const pixels = original.current;
    if (!context || !pixels || !histogram.length) return;
    if (channel === 'RGB') {
      context.putImageData(pixels, 0, 0);
      return;
    }
    const displayed = new ImageData(new Uint8ClampedArray(pixels.data), pixels.width, pixels.height);
    const index = channels.indexOf(channel) - 1;
    for (let offset = 0; offset < displayed.data.length; offset += 4) {
      const value = pixels.data[offset + index];
      displayed.data.fill(value, offset, offset + 3);
    }
    context.putImageData(displayed, 0, 0);
  }, [channel, histogram]);

  if (!evidence.source || evidence.type === 'audio') return <div className="inspection-panel">
    <h3>{translate("Visual inspection")}</h3><p>{translate("Open an image or video with available source media to inspect its pixels.")}</p>
  </div>;

  const peak = Math.max(1, ...histogram.flat());
  return <section className="inspection-panel" aria-label={translate("Visual inspection")}>
    {evidence.type === 'image' ? <img hidden crossOrigin={evidence.preserved?'anonymous':undefined} src={evidence.source} alt="" onLoad={event=>capture(event.currentTarget)} onError={()=>setError('Image could not be decoded.')}/> :
      <div className="inspection-video">
        <video ref={video} crossOrigin={evidence.preserved?'anonymous':undefined} src={evidence.source} controls preload="metadata" onLoadedMetadata={event=>{
          if (Number.isFinite(event.currentTarget.duration)) event.currentTarget.currentTime = Math.min(positionMs / 1000, event.currentTarget.duration);
        }} onError={()=>setError('Video could not be decoded.')}/>
        <button className="button secondary" onClick={()=>{if(video.current){video.current.pause();capture(video.current)}}}>{translate("Inspect current frame")}</button>
      </div>}
    <div className="inspection-controls">
      <label>{translate("Channel")}<select value={channel} onChange={event=>setChannel(event.target.value as Channel)}>{channels.map(value=><option key={value}>{value}</option>)}</select></label>
      <label>{translate("Brightness")} <input type="range" min="50" max="150" value={brightness} onChange={event=>setBrightness(+event.target.value)}/></label>
      <label>{translate("Contrast")} <input type="range" min="50" max="150" value={contrast} onChange={event=>setContrast(+event.target.value)}/></label>
      <button className="button secondary" onClick={()=>{setChannel('RGB');setBrightness(100);setContrast(100)}}>{translate("Reset view")}</button>
    </div>
    {error&&<p role="alert">{error}</p>}
    <canvas ref={canvas} hidden={!histogram.length} aria-label={`${sample} · ${channel} preview`} style={{filter:`brightness(${brightness}%) contrast(${contrast}%)`}}/>
    {!!histogram.length&&<div className="inspection-plot">
      <h3>{translate("RGB intensity histogram")}</h3>
      <p>{sample} · {original.current?.width} × {original.current?.height} {translate("preview pixels · measured before view adjustments")}</p>
      <div className="inspection-bars" aria-label={translate("Pixel counts in 32 intensity bins")}>
        {Array.from({length:32},(_,bin)=><div key={bin}>{histogram.map((series,rgb)=><i key={rgb}
          title={`${channels[rgb+1]} ${bin*8}–${bin*8+7}: ${series[bin]} pixels`}
          style={{height:`${series[bin]/peak*100}%`,background:colors[rgb]}}/>)}</div>)}
      </div>
      <div className="inspection-axis"><span>{translate("0 · Dark")}</span><span>{translate("255 · Light")}</span></div>
    </div>}
    <p>{translate("Display adjustments and pixel measurements are visual inspection aids.")}</p>
  </section>;
}

export function ReferenceComparison({evidence, items}: {evidence: Evidence; items: Evidence[]}) {
  const candidates = items.filter(item=>item.id!==evidence.id && item.type==='image' && item.source);
  const [referenceId,setReferenceId] = useState('');
  const reference = candidates.find(item=>item.id===referenceId);
  if (evidence.type!=='image'||!evidence.source) return <div className="inspection-panel">
    <h3>{translate("Reference comparison")}</h3><p>{translate("Open an image with available source media to compare it against another image in this case.")}</p>
  </div>;
  return <section className="inspection-panel" aria-label={translate("Reference comparison")}>
    <label className="field">{translate("Reference image")}<select value={reference?.id||''} onChange={event=>setReferenceId(event.target.value)}>
      <option value="">{candidates.length?'Select a case image':'Add a second image to this case'}</option>
      {candidates.map(item=><option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}
    </select></label>
    <div className="inspection-comparison">
      <figure><figcaption>{translate("Evidence ·")} {evidence.name}</figcaption><img src={evidence.source} alt={`Evidence: ${evidence.name}`}/></figure>
      <figure><figcaption>{translate("Reference ·")} {reference?.name||'Select an image'}</figcaption>
        {reference&&<img src={reference.source} alt={`Reference: ${reference.name}`}/>}
      </figure>
    </div>
    {reference&&evidence.hash&&reference.hash&&<p>{translate("Recorded SHA-256 values")} {evidence.hash.toLowerCase()===reference.hash.toLowerCase()?'match':'differ'}.</p>}
  </section>;
}
