import {z} from 'zod';
import {formatRelativeTime} from '../i18n/formatters';
import {translate,type Language} from '../i18n';

export const caseEventTypes=['case.created','evidence.registered','run.started','run.completed','run.failed','run.partial','note.added','finding.created'] as const;
export type CaseEventType=typeof caseEventTypes[number];
export const caseEventSchema=z.object({id:z.string(),type:z.enum(caseEventTypes),case_id:z.string(),evidence_id:z.string().nullable(),run_id:z.string().nullable(),actor:z.string(),created_at:z.string().datetime({offset:true}),summary:z.string(),payload:z.record(z.string(),z.unknown())});
const pageSchema=z.object({items:z.array(caseEventSchema),next_cursor:z.string().nullable()});
export type CaseEvent=z.infer<typeof caseEventSchema>;
export type ActivityFilters={type?:CaseEventType;evidenceId?:string;actor?:string;from?:string;to?:string};

export function relativeTime(value:string,now=Date.now(),language:Language='en'):string{const seconds=Math.round((Date.parse(value)-now)/1000),absolute=Math.abs(seconds);if(absolute<60)return translate('time.justNow',undefined,language);const units:[number,Intl.RelativeTimeFormatUnit][]=[[86400,'day'],[3600,'hour'],[60,'minute']];const [size,unit]=units.find(([size])=>absolute>=size)!;return formatRelativeTime(Math.round(seconds/size),unit,language)}
export function parseActivityFilters(parameters:URLSearchParams):ActivityFilters{const type=parameters.get('type');return{...(caseEventTypes.includes(type as CaseEventType)?{type:type as CaseEventType}:{}),...(parameters.get('evidence')?{evidenceId:parameters.get('evidence')!}:{}),...(parameters.get('actor')?{actor:parameters.get('actor')!}:{}),...(parameters.get('from')?{from:parameters.get('from')!}:{}),...(parameters.get('to')?{to:parameters.get('to')!}:{})}}
export function serializeActivityFilters(filters:ActivityFilters):string{const values=new URLSearchParams();if(filters.type)values.set('type',filters.type);if(filters.evidenceId)values.set('evidence',filters.evidenceId);if(filters.actor)values.set('actor',filters.actor);if(filters.from)values.set('from',filters.from);if(filters.to)values.set('to',filters.to);return values.toString()}
export const appendEventPage=(current:CaseEvent[],next:CaseEvent[])=>[...current,...next.filter(event=>!current.some(existing=>existing.id===event.id))];

export class CaseEventsApi{
 constructor(private baseUrl:string,private fetchImpl:typeof fetch=globalThis.fetch.bind(globalThis) as typeof fetch){}
 async list(caseId:string,filters:ActivityFilters={},cursor?:string,limit=25){const query=new URLSearchParams({limit:String(limit)});if(filters.type)query.set('type',filters.type);if(filters.evidenceId)query.set('evidence_id',filters.evidenceId);if(filters.actor)query.set('actor',filters.actor);if(filters.from)query.set('from',new Date(filters.from).toISOString());if(filters.to)query.set('to',new Date(filters.to).toISOString());if(cursor)query.set('cursor',cursor);const response=await this.fetchImpl(`${this.baseUrl.replace(/\/$/,'')}/api/cases/${encodeURIComponent(caseId)}/events?${query}`);const body:unknown=await response.json().catch(()=>null);if(!response.ok)throw new Error(typeof(body as {detail?:unknown})?.detail==='string'?(body as {detail:string}).detail:`Activity API returned HTTP ${response.status}.`);return pageSchema.parse(body)}
}
