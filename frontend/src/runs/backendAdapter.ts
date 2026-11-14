import type {RunStatus} from './types';
export type AdaptedStatus={status:RunStatus;original:string;reason:string|null};
export function fromBackendRunStatus(value:unknown):AdaptedStatus{if(value==='unavailable')return {status:'unsupported',original:value,reason:'capability_unavailable'};if(['queued','running','completed','partial','failed','cancelled','unsupported'].includes(String(value)))return {status:value as RunStatus,original:String(value),reason:null};return {status:'failed',original:String(value),reason:'unknown_backend_status'}}
