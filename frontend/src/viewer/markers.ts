import type {Finding} from '../model';
import type {ViewerInterval} from './selection';

export type TimeMarker={findingId:string;positionMs:number;interval:ViewerInterval|null;tone:'danger'|'warning'|'neutral'};
const completed=(finding:Finding)=>finding.execution_status==='completed';
export function findingInterval(finding:Finding):ViewerInterval|null{
 if(!completed(finding)||!finding.location)return null;const location=finding.location;
 if((location.kind==='time_range'||(!location.kind&&location.start_ms!=null))&&location.start_ms!=null&&location.end_ms!=null&&location.end_ms>location.start_ms)return{startMs:location.start_ms,endMs:location.end_ms};
 return null;
}
export function findingPositionMs(finding:Finding):number|null{
 if(!completed(finding)||!finding.location)return null;const location=finding.location;
 const interval=findingInterval(finding);if(interval)return interval.startMs;
 if(location.kind==='point'&&location.timestamp_ms!=null)return location.timestamp_ms;
 if(location.kind==='region'&&location.frame_timestamp_ms!=null)return location.frame_timestamp_ms;
 return null;
}
export function extractTimeMarkers(findings:Finding[]):TimeMarker[]{return findings.flatMap(finding=>{const positionMs=findingPositionMs(finding);if(positionMs==null)return[];return[{findingId:finding.finding_id,positionMs,interval:findingInterval(finding),tone:finding.result==='indicators_detected'?'danger':finding.result==='inconclusive'?'warning':'neutral'}]})}
export function overlappingFindingIds(findings:Finding[],selection:ViewerInterval|null,positionMs:number):Set<string>{const point={startMs:positionMs,endMs:positionMs+1};return new Set(findings.filter(f=>{const interval=findingInterval(f);return interval?intervalsTouch(interval,selection??point):findingPositionMs(f)!=null&&Math.abs(findingPositionMs(f)!-positionMs)<=40}).map(f=>f.finding_id))}
const intervalsTouch=(a:ViewerInterval,b:ViewerInterval)=>a.startMs<b.endMs&&b.startMs<a.endMs;
