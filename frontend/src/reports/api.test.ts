import {afterEach,describe,expect,it,vi} from 'vitest';
import {reportApi,savedReportSchema} from './api';

const snapshot={schema_version:'d5.1',report_id:'RPT-test',revision:1,generated_at:'2026-11-13T10:00:00Z',
 preparer:'Bhumi',preparer_verified:false,case:{id:'CASE-2026-000001',title:'Test case',description:'',status:'open',
 created_at:'2026-11-13T10:00:00Z',last_activity_at:'2026-11-13T10:00:00Z',created_by:'Bhumi',created_by_verified:false,
 evidence_count:0,evidence_by_media_type:{image:0,audio:0,video:0}},evidence:[],findings:[],review_notes:{},coverage:[],fixture:false,review_status:'unreviewed',limitations:['No inference performed.']};

afterEach(()=>vi.unstubAllGlobals());
describe('D5 report API',()=>{
 it('validates byte-verification claims separately from artifact metadata',()=>{
  const artifact={reference:'D2-artifact',finding_id:'F-1',run_id:'D2RUN-test',evidence_id:'E-1',
   status:'verified',metadata:{sha256:'b'.repeat(64)},bytes_verified:true,bytes_included:true,zip_path:`artifacts/${'b'.repeat(64)}.bin`};
  const report={snapshot:{...snapshot,schema_version:'d5.7',source_references:{runs:[],artifacts:[artifact],limitations:[]}},sha256:'a'.repeat(64)};
  expect(savedReportSchema.parse(report).snapshot.source_references?.artifacts[0].bytes_verified).toBe(true);
  expect(()=>savedReportSchema.parse({...report,snapshot:{...report.snapshot,source_references:{...report.snapshot.source_references,artifacts:[{...artifact,bytes_verified:false}]}}})).toThrow('Verified artifact flags');
 });
 it('records a review against the selected saved report without sending case findings',async()=>{
  const reviewed={...snapshot,schema_version:'d5.4',revision:2,review_status:'questioned',prepared_at:snapshot.generated_at,
   parent_report_id:'RPT-test',parent_report_sha256:'b'.repeat(64),
   review_history:[{reviewer:'Bhumi',reviewer_verified:false,status:'questioned',note:'Need source confirmation',reviewed_at:snapshot.generated_at,source_report_id:'RPT-test',source_report_sha256:'b'.repeat(64)}]};
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({snapshot:reviewed,sha256:'a'.repeat(64)})));
  vi.stubGlobal('fetch',fetch);
  const result=await reportApi('').review('RPT-test','Bhumi','questioned','Need source confirmation');
  expect(fetch.mock.calls[0][0]).toBe('/api/reports/RPT-test/reviews');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({reviewer:'Bhumi',status:'questioned',note:'Need source confirmation'});
  expect(result.snapshot.review_status).toBe('questioned');
 });
 it('rejects reviewed labels without linked reviewer history',()=>{
  expect(()=>savedReportSchema.parse({snapshot:{...snapshot,review_status:'reviewed'},sha256:'a'.repeat(64)})).toThrow('reviewer history');
 });
 it('sends chosen readable sections with the save request',async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({snapshot,sha256:'a'.repeat(64)})));
  vi.stubGlobal('fetch',fetch);
  await reportApi('').save('CASE-2026-000001','Bhumi',undefined,['methods','findings','coverage','limitations']);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({preparer:'Bhumi',sections:['methods','findings','coverage','limitations']});
 });
 it('sends explicit selected run IDs to the reporting API',async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({snapshot,sha256:'a'.repeat(64)})));
  vi.stubGlobal('fetch',fetch);
  await reportApi('').save('CASE-2026-000001','Bhumi',['RUN-1']);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({preparer:'Bhumi',run_ids:['RUN-1']});
 });
 it('loads run options and validates their selection state',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[{run_id:'RUN-1',status:'running',selectable:false,status_source:'run_record',finding_count:1,evidence_ids:['E-1']}]}))));
  const options=await reportApi('').runOptions('CASE-2026-000001');
  expect(options[0].selectable).toBe(false);
 });
 it('saves only preparer input; findings are sourced on the server',async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({snapshot,sha256:'a'.repeat(64)})));
  vi.stubGlobal('fetch',fetch);
  const saved=await reportApi('http://localhost:8000/').save('CASE-2026-000001','Bhumi');
  expect(saved.snapshot.report_id).toBe('RPT-test');
  expect(fetch.mock.calls[0][0]).toBe('http://localhost:8000/api/cases/CASE-2026-000001/reports');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({preparer:'Bhumi'});
 });
 it('surfaces API errors without browser-local fallback',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Saved report failed SHA-256 verification'}),{status:409})));
  await expect(reportApi('').get('RPT-test')).rejects.toThrow('SHA-256 verification');
 });
 it('rejects malformed report data before preview',()=>{
  expect(()=>savedReportSchema.parse({snapshot:{...snapshot,revision:0},sha256:'invalid'})).toThrow();
 });
 it('forwards cancellation when loading revisions',async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[]})));
  vi.stubGlobal('fetch',fetch);const controller=new AbortController();
  await reportApi('').list('case/one',controller.signal);
  expect(fetch.mock.calls[0][0]).toBe('/api/cases/case%2Fone/reports');
  expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
 });
});
