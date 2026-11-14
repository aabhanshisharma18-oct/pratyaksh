import {translate} from '../i18n';
import {useRef, useState, type PointerEvent} from 'react';

export type ShadowLine = {id: string; start: [number,number]; end: [number,number]};

export function ShadowInspection({src,lines,onChange}: {
  src: string;
  lines: ShadowLine[];
  onChange: (lines: ShadowLine[])=>void;
}) {
  const [size,setSize] = useState({width:1,height:1});
  const [draft,setDraft] = useState<ShadowLine>();
  const surface = useRef<SVGSVGElement>(null);

  function point(event: PointerEvent<SVGSVGElement>): [number,number] {
    const bounds = event.currentTarget.getBoundingClientRect();
    return [Math.max(0,Math.min(1,(event.clientX-bounds.left)/bounds.width)),
      Math.max(0,Math.min(1,(event.clientY-bounds.top)/bounds.height))];
  }

  function finish(event: PointerEvent<SVGSVGElement>) {
    if (!draft) return;
    const end = point(event);
    const distance = Math.hypot((end[0]-draft.start[0])*size.width,(end[1]-draft.start[1])*size.height);
    if (distance>3) onChange([...lines,{...draft,end}]);
    setDraft(undefined);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  return <div className="shadow-inspection">
    <p>{translate("Drag from an object toward its shadow to add a measurement line.")}</p>
    <div className="shadow-image">
      <img src={src} alt={translate("Evidence for manual shadow inspection")}
        onLoad={event=>setSize({width:event.currentTarget.naturalWidth,height:event.currentTarget.naturalHeight})}/>
      <svg ref={surface} viewBox={'0 0 '+size.width+' '+size.height} preserveAspectRatio="none"
        role="img" aria-label={translate("Manual shadow measurement lines")}
        onPointerDown={event=>{
          if (event.button!==0) return;
          const start=point(event);
          event.currentTarget.setPointerCapture(event.pointerId);
          setDraft({id:crypto.randomUUID(),start,end:start});
        }}
        onPointerMove={event=>{if(draft)setDraft({...draft,end:point(event)});}}
        onPointerUp={finish} onPointerCancel={()=>setDraft(undefined)}>
        {[...lines,...(draft?[draft]:[])].map((line,index)=><g key={line.id}>
          <line x1={line.start[0]*size.width} y1={line.start[1]*size.height}
            x2={line.end[0]*size.width} y2={line.end[1]*size.height} stroke="#00ad83" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
          <circle cx={line.start[0]*size.width} cy={line.start[1]*size.height} r="4" fill="#00ad83" vectorEffect="non-scaling-stroke"/>
          <text x={line.start[0]*size.width+8} y={line.start[1]*size.height-7}
            fontSize={Math.max(12,size.width/55)} fill="#00644d">{index+1}</text>
        </g>)}
      </svg>
    </div>
    {lines.length>0 && <table><thead><tr><th>{translate("Line")}</th><th>{translate("Start (px)")}</th><th>{translate("End (px)")}</th><th>{translate("Direction")}</th><th/></tr></thead>
      <tbody>{lines.map((line,index)=>{
        const dx=(line.end[0]-line.start[0])*size.width,dy=(line.end[1]-line.start[1])*size.height;
        return <tr key={line.id}><th scope="row">{index+1}</th>
          <td>{Math.round(line.start[0]*size.width)}, {Math.round(line.start[1]*size.height)}</td>
          <td>{Math.round(line.end[0]*size.width)}, {Math.round(line.end[1]*size.height)}</td>
          <td>{((Math.atan2(dy,dx)*180/Math.PI+360)%360).toFixed(1)}°</td>
          <td><button type="button" aria-label={'Remove shadow line '+(index+1)} onClick={()=>onChange(lines.filter(item=>item.id!==line.id))}>{translate("Remove")}</button></td>
        </tr>;
      })}</tbody></table>}
    <p>{translate("Manual image-plane measurements. Review perspective, surfaces, and light sources when interpreting directions.")}</p>
  </div>;
}
