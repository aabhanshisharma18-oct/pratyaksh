import type {Finding} from '../model';

export type RegionBox={id:string;findingId:string;left:string;top:string;width:string;height:string;label:string;tone:'danger'|'warning'|'neutral';frameMs:number|null};
export function regionToCss(input:{x?:number;y?:number;width?:number;height?:number}):Pick<RegionBox,'left'|'top'|'width'|'height'>|null{
 const{x,y,width,height}=input;if(![x,y,width,height].every(Number.isFinite)||x==null||y==null||width==null||height==null||width<=0||height<=0||x<0||y<0||x+width>1||y+height>1){if(typeof console!=='undefined')console.warn('Skipped invalid normalized evidence region',input);return null}
 return{left:`${x*100}%`,top:`${y*100}%`,width:`${width*100}%`,height:`${height*100}%`};
}
export function extractRegions(findings:Finding[]):RegionBox[]{return findings.flatMap(finding=>{if(finding.execution_status!=='completed'||finding.location?.kind!=='region')return[];const box=regionToCss(finding.location);if(!box)return[];return[{...box,id:`region-${finding.finding_id}`,findingId:finding.finding_id,label:finding.location.label?.toLowerCase().includes('candidate')?'candidate region · not a measured mask':finding.location.label||'illustrative region',tone:finding.result==='indicators_detected'?'danger':finding.result==='inconclusive'?'warning':'neutral',frameMs:finding.location.frame_timestamp_ms??null}]})}
export function visibleAtPosition(region:RegionBox,positionMs:number,toleranceMs=80):boolean{return region.frameMs==null||Math.abs(region.frameMs-positionMs)<=toleranceMs}
