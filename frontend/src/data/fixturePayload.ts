import {wrappedCatalogueSchema,wrappedRunSchema,type FixtureRun} from '../fixtureSchemas';
import type {CaseRecord,Evidence,Finding} from '../model';
export async function loadFixturePayload(){
 const [catalogueModule,...runModules]=await Promise.all([import('../../../fixtures/dev/case-evidence.json'),import('../../../fixtures/dev/runs/RUN-00a4.json'),import('../../../fixtures/dev/runs/RUN-00a5.json'),import('../../../fixtures/dev/runs/RUN-00a6.json'),import('../../../fixtures/dev/runs/RUN-00a7.json'),import('../../../fixtures/dev/runs/RUN-00a8.json'),import('../../../fixtures/dev/runs/RUN-00a9.json')]);
 const catalogue=wrappedCatalogueSchema.parse(catalogueModule.default).data;
 const runs:FixtureRun[]=runModules.map(module=>wrappedRunSchema.parse(module.default).data);
 const cases:CaseRecord[]=[catalogue.case];
 const evidence:Evidence[]=catalogue.evidence.map(item=>({id:item.evidence_id,name:item.filename,type:item.media_type,role:item.role,size:`${(item.size_bytes/1024/1024).toFixed(1)} MB`,duration:item.duration,received:item.registered_at,hash:item.sha256,fixture:true,status:item.status,dimensions:item.dimensions}));
 return {cases,evidence,runs,findings:runs.flatMap(run=>run.findings) as Finding[]};
}
