import {translate} from '../i18n';
import {AlertTriangle,Loader2,RotateCw} from 'lucide-react';

export function AsyncState({state,message,onRetry}:{state:'loading'|'empty'|'error';message:string;onRetry?:()=>void}){return <div className={`async-state ${state}`} role={state==='error'?'alert':'status'} aria-live="polite" aria-busy={state==='loading'}>{state==='loading'?<Loader2 className="spin" aria-hidden="true"/>:state==='error'?<AlertTriangle aria-hidden="true"/>:null}<span>{message}</span>{state==='error'&&onRetry&&<button type="button" className="button secondary" onClick={onRetry}><RotateCw size={14}/>{translate("Retry")}</button>}</div>}
