import {wrappedCatalogueSchema,wrappedRunSchema,type FixtureRun} from '../fixtureSchemas';
import type {CaseRecord,Evidence,Finding} from '../model';
import type {RunRecord} from '../runs/types';
export async function loadFixturePayload(){
 const [catalogueModule,...runModules]=await Promise.all([import('../../../fixtures/dev/case-evidence.json'),import('../../../fixtures/dev/runs/RUN-00a4.json'),import('../../../fixtures/dev/runs/RUN-00a5.json'),import('../../../fixtures/dev/runs/RUN-00a6.json'),import('../../../fixtures/dev/runs/RUN-00a7.json'),import('../../../fixtures/dev/runs/RUN-00a8.json'),import('../../../fixtures/dev/runs/RUN-00a9.json'),import('../../../fixtures/dev/runs/RUN-00aa.json'),import('../../../fixtures/dev/runs/RUN-00ab.json'),import('../../../fixtures/dev/runs/RUN-00ac.json'),import('../../../fixtures/dev/runs/RUN-00ad.json'),import('../../../fixtures/dev/runs/RUN-00ae.json')]);
 const catalogue=wrappedCatalogueSchema.parse(catalogueModule.default).data;
 const parsedRuns:FixtureRun[]=runModules.map(module=>wrappedRunSchema.parse(module.default).data);
 const runs:RunRecord[]=parsedRuns.map(run=>({...run,requested_at:run.requested_at??run.started_at??'2026-10-30T00:00:00Z',origin:run.origin??'fixture',attempt:run.attempt??1,retry_of:run.retry_of??null,requested_channels:run.requested_channels??['synthetic_media','tampering','integrity','provenance'],status_reason:run.status_reason??null,findings:run.findings as Finding[]}));
 const cases:CaseRecord[]=[catalogue.case];
 const evidence:Evidence[]=catalogue.evidence.map(item=>({id:item.evidence_id,name:item.filename,type:item.media_type,role:item.role,size:`${(item.size_bytes/1024/1024).toFixed(1)} MB`,duration:item.duration,received:item.registered_at,hash:item.sha256,fixture:true,status:item.status,dimensions:item.dimensions}));
 return {cases,evidence,runs,findings:runs.flatMap(run=>run.findings) as Finding[]};
}
