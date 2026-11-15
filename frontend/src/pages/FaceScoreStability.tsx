import {useState, useEffect, useRef} from 'react';
import {z} from 'zod';
import './face-score-stability.css';

const resultSchema = z.object({
  sha256: z.string(), model_id: z.string(), model_version: z.string(),
  checkpoint_sha256: z.string().nullable(),
  comparison_sha256: z.string().nullable().optional(),
  versions: z.array(z.object({
    label: z.string(), thumbnail: z.string(), width: z.number(), height: z.number(),
    faces: z.array(z.object({
      score: z.number().min(0).max(1),
      box: z.tuple([z.number(), z.number(), z.number(), z.number()]),
    }).nullable()),
  })).min(1),
});

export function FaceScoreStability({baseUrl, loadImage, expectedHash, initialFace = 0}: {
  baseUrl: string;
  loadImage: (signal: AbortSignal) => Promise<Blob>;
  expectedHash?: string;
  initialFace?: number;
}) {
  const [result, setResult] = useState<z.infer<typeof resultSchema>>();
  const [faceIndex, setFaceIndex] = useState(0);
  const [comparison, setComparison] = useState<File>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController>();
  useEffect(() => () => request.current?.abort(), []);

  async function compare() {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    setResult(undefined);
    try {
      const image = await loadImage(controller.signal);
      const form = new FormData();
      form.set('file', image, 'evidence-image');
      if (comparison) form.set('comparison', comparison, comparison.name);
      const proxy = import.meta.env.DEV && baseUrl === import.meta.env.VITE_D1_API_BASE_URL?.trim();
      const response = await fetch((proxy ? '' : baseUrl.replace(/\/$/, '')) + '/api/d1/face-score-stability',
        {method: 'POST', body: form, signal: controller.signal});
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The SBI comparison failed. Check the detection backend.');
      const parsed = resultSchema.parse(body);
      if (expectedHash && parsed.sha256 !== expectedHash.toLowerCase()) {
        throw new Error('The photo does not match the evidence fingerprint.');
      }
      setFaceIndex(initialFace < parsed.versions[0].faces.length ? initialFace : 0);
      setResult(parsed);
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'The comparison could not run.');
    } finally {
      if (request.current === controller) request.current = undefined;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  const original = result?.versions[0].faces[faceIndex]?.score;
  return <section className="face-stability" aria-label="SBI score stability" aria-busy={busy}>
    <h3>SBI score stability</h3>
    <p>Choose a copy with the same framing, or let Pratyaksh make test copies.</p>
    <label>Comparison image (optional)
      <input type="file" accept="image/jpeg,image/png,image/webp,.heic,.heif" disabled={busy}
        onChange={event => {setComparison(event.target.files?.[0]); setResult(undefined); setError('');}}/>
    </label>
    <button type="button" className="button secondary" onClick={compare} disabled={busy || !baseUrl}>
      {busy ? 'Comparing image versions…' : comparison ? 'Compare both images' : 'Test score stability'}
    </button>
    {error && <p role="alert">{error}</p>}
    {result && (original === undefined ? <p role="status">SBI could not score a face in the uploaded photo.</p> : <>
      <label>Examined face <select value={faceIndex} onChange={event => setFaceIndex(Number(event.target.value))}>
        {result.versions[0].faces.map((_, index) => <option key={index} value={index}>Face {index + 1}</option>)}
      </select></label>
      <div className="face-stability-grid">
        {result.versions.map((version, index) => {
          const face = version.faces[faceIndex];
          const delta = face ? face.score - original : null;
          return <article key={version.label}>
            <strong>{version.label}</strong>
            <div className="face-stability-preview">
              <img src={'data:image/jpeg;base64,' + version.thumbnail} alt={version.label}/>
              {face && <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
                <rect x={face.box[0]} y={face.box[1]} width={face.box[2] - face.box[0]}
                  height={face.box[3] - face.box[1]} vectorEffect="non-scaling-stroke"/>
              </svg>}
            </div>
            <small>{version.width} × {version.height} px</small>
            <p>{face ? <>SBI score <strong>{face.score.toFixed(3)}</strong>
              {index > 0 && delta !== null && <> · Δ {delta > 0 ? '+' : ''}{delta.toFixed(3)}</>}</>
              : 'Could not score this face'}</p>
          </article>;
        })}
      </div>
      <div aria-live="polite">
        {result.versions.slice(1).map(version => {
          const score = version.faces[faceIndex]?.score;
          const direction = score === undefined ? null : score.toFixed(3) === original.toFixed(3)
            ? 'stayed the same to three decimal places' : score < original ? 'decreased' : 'increased';
          return <p key={version.label}><strong>{version.label}:</strong>{' '}
            {direction ? `The face-manipulation signal ${direction}.` : 'SBI did not return a score for a clear match to this face.'}</p>;
        })}
        <p>Score changes show how SBI responded to these copies.</p>
      </div>
      <details><summary>Model and input fingerprint</summary>
        <p>{result.model_id} · {result.model_version}</p>
        <p>Input SHA-256 <code>{result.sha256}</code></p>
        {result.comparison_sha256 && <p>Comparison SHA-256 <code>{result.comparison_sha256}</code></p>}
        {result.checkpoint_sha256 && <p>Checkpoint SHA-256 <code>{result.checkpoint_sha256}</code></p>}
      </details>
    </>)}
  </section>;
}
