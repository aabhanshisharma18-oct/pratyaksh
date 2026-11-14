import {clampMs} from './timeFormat';

export type ViewerInterval={startMs:number;endMs:number};
export type ViewerSelection={positionMs:number;interval:ViewerInterval|null;findingId:string|null;regionId:string|null;flaggedIndex:number|null};
export const emptySelection:ViewerSelection={positionMs:0,interval:null,findingId:null,regionId:null,flaggedIndex:null};
export type SelectionAction=
 |{type:'reset';value?:Partial<ViewerSelection>}
 |{type:'seek';positionMs:number;durationMs?:number}
 |{type:'interval';startMs:number;endMs:number;durationMs?:number;findingId?:string|null}
 |{type:'set-start';durationMs?:number}|{type:'set-end';durationMs?:number}
 |{type:'finding';findingId:string;positionMs?:number;interval?:ViewerInterval|null;regionId?:string|null;flaggedIndex?:number|null;durationMs?:number}
 |{type:'clear'};

export function normalizeInterval(startMs:number,endMs:number,durationMs=Number.POSITIVE_INFINITY):ViewerInterval|null{
 const start=clampMs(Math.min(startMs,endMs),durationMs),end=clampMs(Math.max(startMs,endMs),durationMs);
 return end>start?{startMs:start,endMs:end}:null;
}
export function intervalsOverlap(a:ViewerInterval,b:ViewerInterval):boolean{return a.startMs<b.endMs&&b.startMs<a.endMs}
export function selectionReducer(state:ViewerSelection,action:SelectionAction):ViewerSelection{
 switch(action.type){
  case'reset':return{...emptySelection,...action.value};
  case'seek':return{...state,positionMs:clampMs(action.positionMs,action.durationMs)};
  case'interval':return{...state,interval:normalizeInterval(action.startMs,action.endMs,action.durationMs),findingId:action.findingId??state.findingId};
  case'set-start':return{...state,interval:normalizeInterval(state.positionMs,state.interval?.endMs??state.positionMs+1,action.durationMs)};
  case'set-end':return{...state,interval:normalizeInterval(state.interval?.startMs??Math.max(0,state.positionMs-1),state.positionMs,action.durationMs)};
  case'finding':return{...state,positionMs:clampMs(action.positionMs??state.positionMs,action.durationMs),interval:action.interval??null,findingId:action.findingId,regionId:action.regionId??null,flaggedIndex:action.flaggedIndex??null};
  case'clear':return{...state,interval:null,findingId:null,regionId:null,flaggedIndex:null};
 }
}
