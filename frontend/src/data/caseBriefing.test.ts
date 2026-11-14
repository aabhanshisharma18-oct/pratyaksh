import {describe,expect,it,vi} from 'vitest';
import {briefingSourceRoute,caseBriefingSchema,explainCase} from './caseBriefing';
import {parseHash} from '../app/routing';

const source={source_id:'S1',kind:'finding' as const,evidence_ids:['E-AUDIO'],media_types:['audio'],observation:'Inconclusive signal',finding_id:'F1',run_id:'RUN1',limitations:['Not calibrated']};
const item={text:'Review the voice scan.',basis:'The result is inconclusive.',source_ids:['S1']};
const briefing={case_id:'CASE-1',snapshot_sha256:'hash',generated_at:'2026-11-14T10:00:00Z',model:'test',cached:false,key_findings:[item],open_questions:[item],next_steps:[item],sources:[source],cautions:[]};

describe('cited case briefing',()=>{
 it('opens a voice finding at its exact evidence, run and finding',()=>{
  expect(parseHash('#'+briefingSourceRoute('CASE-1',source))).toMatchObject({caseId:'CASE-1',evidenceId:'E-AUDIO',findingId:'F1',runId:'RUN1',page:'Workbench'});
 });
 it('opens the specific saved image comparison rather than the latest report',()=>{
  const path=briefingSourceRoute('CASE-1',{...source,kind:'relationship',analysis_id:'PROV-1',relationship_id:'EDGE&2'});
  expect(parseHash('#'+path)).toMatchObject({page:'Provenance',caseId:'CASE-1',analysisId:'PROV-1',relationshipId:'EDGE&2'});
 });
 it('rejects fabricated citations',()=>{
  expect(caseBriefingSchema.safeParse({...briefing,key_findings:[{...item,source_ids:['OTHER_CASE']}]}).success).toBe(false);
 });
 it('posts only the case identifier, with no raw media or client supplied findings',async()=>{
  const send=vi.fn().mockResolvedValue(new Response(JSON.stringify(briefing)));
  await explainCase('http://localhost:8000/','CASE-1',new AbortController().signal,send);
  const [url,init]=send.mock.calls[0];
  expect(url).toBe('http://localhost:8000/api/cases/CASE-1/briefing');
  expect(init.method).toBe('POST');expect(init.body).toBeUndefined();
 });
 it('does not display a response from another case',async()=>{
  const send=vi.fn().mockResolvedValue(new Response(JSON.stringify({...briefing,case_id:'CASE-OTHER'})));
  await expect(explainCase('', 'CASE-1',new AbortController().signal,send)).rejects.toThrow('matched to this case');
 });
 it('shows provider quota errors without replacing saved forensic results',async()=>{
  const send=vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Free quota reached.'}),{status:429}));
  await expect(explainCase('', 'CASE-1',new AbortController().signal,send)).rejects.toThrow('Free quota reached');
 });
});
