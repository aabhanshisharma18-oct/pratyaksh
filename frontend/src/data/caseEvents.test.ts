import {describe,expect,it,vi} from 'vitest';
import {appendEventPage,CaseEventsApi,parseActivityFilters,relativeTime,serializeActivityFilters,type CaseEvent} from './caseEvents';

const event:CaseEvent={id:'EVT-1',type:'run.partial',case_id:'CASE-1',evidence_id:'EVID-1',run_id:'RUN-1',actor:'Analysis service',created_at:'2026-11-12T10:00:00Z',summary:'Run partial',payload:{status:'partial'}};
describe('case activity frontend data',()=>{
 it('formats relative activity while preserving absolute timestamps for the UI title',()=>expect(relativeTime(event.created_at,Date.parse('2026-11-12T12:00:00Z'))).toBe('2 hours ago'));
 it('round-trips shareable filters',()=>{const filters={type:'run.partial' as const,evidenceId:'EVID-1',actor:'Aadya',from:'2026-11-01T00:00'};expect(parseActivityFilters(new URLSearchParams(serializeActivityFilters(filters)))).toEqual(filters)});
 it('appends cursor pages without duplicate events',()=>expect(appendEventPage([event],[event,{...event,id:'EVT-2'}])).toHaveLength(2));
 it('loads an empty overview state and sends cursor filters',async()=>{const fetcher=vi.fn(async(_input:RequestInfo|URL)=>new Response(JSON.stringify({items:[],next_cursor:null}),{status:200,headers:{'content-type':'application/json'}}));const page=await new CaseEventsApi('http://api',fetcher as typeof fetch).list('CASE-1',{type:'run.failed',evidenceId:'EVID-1'},'opaque',5);expect(page.items).toEqual([]);expect(String(fetcher.mock.calls[0][0])).toContain('type=run.failed');expect(String(fetcher.mock.calls[0][0])).toContain('cursor=opaque')});
});
