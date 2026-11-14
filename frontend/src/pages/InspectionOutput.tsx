import {translate} from '../i18n';
import {useState} from 'react';
import type {InspectionResult} from './imageInspection';

export function InspectionOutput({result}: {result: InspectionResult}) {
  const [selected,setSelected] = useState<number|null>(null);
  const values = result.chart ?? [];
  const minimum = Math.min(0,...values);
  const maximum = Math.max(1,...values);
  const xAt = (index: number) => 44 + index * 440 / Math.max(1,values.length-1);
  const yAt = (value: number) => 142 - (value-minimum)/(maximum-minimum)*116;
  const selectedValue = selected===null ? undefined : values[selected];
  return <>
    {result.detail && <p role="status">{result.detail}</p>}
    {values.length > 0 && <div className="inspection-chart">
      <svg viewBox="0 0 520 190" role="img" aria-label={result.chartTitle||'Filter results plot'}
        onMouseMove={event=>{
          const bounds = event.currentTarget.getBoundingClientRect();
          const x = (event.clientX-bounds.left)/bounds.width*520;
          setSelected(Math.max(0,Math.min(values.length-1,Math.round((x-44)/440*(values.length-1)))));
        }} onMouseLeave={()=>setSelected(null)}>
        {[0,.25,.5,.75,1].map(fraction=><g key={fraction}>
          <path d={'M44 '+(142-fraction*116)+'H484'} className="inspection-grid"/>
          <text x="38" y={146-fraction*116} textAnchor="end">{Number((minimum+fraction*(maximum-minimum)).toPrecision(3))}</text>
          <path d={'M'+(44+fraction*440)+' 26V142'} className="inspection-grid"/>
        </g>)}
        <path d="M44 26V142H484" fill="none" stroke="currentColor" opacity=".5"/>
        <polyline fill="none" stroke="currentColor" strokeWidth="2"
          points={values.map((value,index)=>xAt(index)+','+yAt(value)).join(' ')}/>
        {[0,Math.floor((values.length-1)/2),values.length-1].filter((value,index,array)=>array.indexOf(value)===index).map(index=>
          <text key={index} x={xAt(index)} y="158" textAnchor="middle">{result.xValues?.[index]??index}</text>)}
        <text x="264" y="180" textAnchor="middle">{result.xLabel||'Bin'}</text>
        <text x="12" y="20">{result.yLabel||'Value'}</text>
        {selectedValue!==undefined && selected!==null && <>
          <path d={'M'+xAt(selected)+' 26V142'} stroke="currentColor" strokeDasharray="3 3"/>
          <circle cx={xAt(selected)} cy={yAt(selectedValue)} r="3" fill="currentColor"/>
        </>}
      </svg>
      <output className="inspection-plot-value" aria-live="off">{selectedValue===undefined ? 'Move over the plot to inspect values.' :
        (result.xLabel||'Bin')+' '+(result.xValues?.[selected!]??selected)+' · '+(result.yLabel||'Value')+' '+Number(selectedValue.toPrecision(5))}</output>
      {!result.rows && <details><summary>{translate("Plot values")}</summary><p>{values.map(value=>Number(value.toFixed(4))).join(', ')}</p></details>}
    </div>}
    {Boolean(result.rows?.length) && <table><thead><tr><th>{translate("Property")}</th><th>{translate("Value")}</th></tr></thead>
      <tbody>{result.rows?.map(([name,value],index)=><tr key={index}><th scope="row">{name}</th><td>{value}</td></tr>)}</tbody>
    </table>}
  </>;
}

export function InspectionComparison({evidence,reference}: {evidence: InspectionResult; reference: InspectionResult}) {
  if (evidence.rows && reference.rows && !evidence.chart && !reference.chart) {
    const left = new Map(evidence.rows);
    const right = new Map(reference.rows);
    const keys = [...new Set([...left.keys(),...right.keys()])];
    return <div className="detection-table-scroll inspection-comparison-table">
      <p>{evidence.detail}</p>
      <table><thead><tr><th>{translate("Property")}</th><th>{translate("Evidence value")}</th><th>{translate("Reference value")}</th><th>{translate("Comparison")}</th></tr></thead>
        <tbody>{keys.map(key=>{
          const matches = left.get(key)===right.get(key);
          return <tr key={key} className={matches?'':'inspection-difference'}>
            <th scope="row">{key}</th><td>{left.get(key)??'Absent'}</td><td>{right.get(key)??'Absent'}</td>
            <td>{matches?'Matches':'Differs'}</td>
          </tr>;
        })}</tbody>
      </table>
      <p>{translate("Differences describe the two files. Review their relevance to the investigation.")}</p>
    </div>;
  }
  return <div className="inspection-compare-grid">
    {([['Evidence',evidence],['Reference',reference]] as const).map(([label,result])=><section key={label} className="detection-table-scroll">
      <h3>{label}</h3>
      {result.image && <img className="inspection-result-image" src={result.image} alt={label+' analysis output'}/>}
      <InspectionOutput result={result}/>
    </section>)}
  </div>;
}
