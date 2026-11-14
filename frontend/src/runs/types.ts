import type {Channel,Finding} from '../model';

export const runStatuses=['queued','running','completed','partial','failed','unsupported','cancelled'] as const;
export type RunStatus=typeof runStatuses[number];
export type RunOrigin='server'|'client'|'fixture';
export type RunError={code:string;message:string;retryable:boolean};
export type RunCoverage={planned:number;examined:number;rejected:number;unexamined:number;percent?:number;duration_ms?:number;strategy?:string|null;sampling_interval_ms?:number;samples:Array<{index:number;timestamp_ms?:number|null;status:'examined'|'rejected'|'unexamined';reason:string|null}>}|null;
export type RunRecord={
 schema_version:'1.1';run_id:string;case_id?:string;evidence_id:string;modality:'image'|'audio'|'video';execution_status:RunStatus;
 requested_at:string;started_at:string|null;completed_at:string|null;configuration:{name:string;version:string};configuration_version?:string;
 findings:Finding[];coverage:RunCoverage;artifacts:Array<{artifact_id:string;kind:string}>;errors:RunError[];fixture:boolean;
 attempt?:number;retry_of?:string|null;retry_children?:string[];origin?:RunOrigin;requested_channels?:Channel[];requested_checks?:string[];status_reason?:string|null;backend_status?:string|null;simulated?:boolean;
};

export const requestedChannels=(run:RunRecord):Channel[]=>run.requested_channels?.length?[...run.requested_channels]:['synthetic_media','tampering','integrity','provenance'];
export const configurationVersion=(run:RunRecord)=>run.configuration_version||run.configuration.version;
export const runAttempt=(run:RunRecord)=>run.attempt??1;
export const runOrigin=(run:RunRecord):RunOrigin=>run.origin||(run.fixture?'fixture':'client');
