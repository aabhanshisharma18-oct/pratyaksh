import {FaceScoreStability} from './FaceScoreStability';
import {translate} from '../i18n';
import {useState} from 'react';
import {faceScoreMeaning} from '../data/scoreMeaning';
import type {FaceAnalysis} from '../data/detectionScan';

export function FaceAnalysisViewer({src,analysis,modelVersion,file,baseUrl,sha256}: {src: string; analysis: FaceAnalysis; modelVersion?: string; file?: File|null; baseUrl?: string; sha256?: string}) {
  const [selected,setSelected] = useState<number|null>(null);
  const [showBoxes,setShowBoxes] = useState(true);
  return <div className="face-analysis">
    <div className="face-analysis-controls">
      <strong>{analysis.face_count} {translate("face")}{analysis.face_count===1?'':'s'} {translate("examined")}</strong>
      <label><input type="checkbox" checked={showBoxes} onChange={event=>setShowBoxes(event.target.checked)}/>{translate("Show face boxes")}</label>
    </div>
    <div className="face-analysis-image">
      <img src={src} alt={translate("Evidence with SBI face analysis")}/>
      {showBoxes && <svg viewBox={'0 0 '+analysis.width+' '+analysis.height} preserveAspectRatio="none" aria-label={translate("Examined face regions")}>
        {analysis.faces.map((face,index)=>{
          const [left,top,right,bottom]=face.bbox_xyxy;
          return <g key={index} className={selected===index?'selected':''}>
            <rect x={left} y={top} width={right-left} height={bottom-top} vectorEffect="non-scaling-stroke"/>
            <text x={left+3} y={top+Math.max(14,analysis.width/55)} fontSize={Math.max(12,analysis.width/60)}
              strokeWidth={Math.max(1,analysis.width/1000)} paintOrder="stroke">
              {translate("Face")} {index+1} · {face.face_forgery_score.toFixed(3)}
            </text>
          </g>;
        })}
      </svg>}
    </div>
    {!analysis.faces.length ? <p>{translate("No face was detected. SBI produced no face score.")}</p> : <>
      <div className="face-analysis-list" aria-label={translate("Per-face SBI scores")}>
        {analysis.faces.map((face,index)=><button key={index} type="button" aria-pressed={selected===index}
          onClick={()=>setSelected(selected===index?null:index)}>
          <strong>{translate("Face")} {index+1}</strong>
          <span>{translate("SBI raw score")} {face.face_forgery_score.toFixed(3)}</span>
          <span>{faceScoreMeaning(face.face_forgery_score,modelVersion)}</span>
        </button>)}
      </div>
      <p>{translate("A low score can miss an edited face. These scores cannot tell you what percentage of a face is AI-generated.")}</p>
    </>}
    {analysis.faces_truncated && <p role="status">{translate("Only the eight largest detected faces were examined.")}</p>}
    {file && baseUrl && analysis.faces.length > 0 && <FaceScoreStability
      baseUrl={baseUrl} loadImage={async () => file} initialFace={selected ?? 0} expectedHash={sha256}/>}
  </div>;
}
