import {describe,expect,it} from 'vitest';
import {classification,findingSchema,tone} from './model';
import {shouldLoadDevelopmentFixtures} from './data/fixtureSource';
import {loadFixturePayload} from './data/fixturePayload';

describe('development fixtures',()=>{
 it('is inert when disabled or API mode is active',()=>{expect(shouldLoadDevelopmentFixtures(false,false)).toBe(false);expect(shouldLoadDevelopmentFixtures(true,true)).toBe(false)});
 it('validates every finding and covers conservative states',async()=>{const fixture=await loadFixturePayload();const findings=fixture.findings;findings.forEach(f=>expect(findingSchema.safeParse(f).success).toBe(true));expect(new Set(findings.map(f=>f.execution_status))).toEqual(new Set(['completed','queued','running','failed','unsupported','not_applicable','cancelled']));expect(findings.some(f=>f.result==='no_indicators_detected')).toBe(true)});
 it('never treats unavailable as clean',async()=>{const fixture=await loadFixturePayload();const finding=fixture.findings.find(f=>f.execution_status==='unsupported')!;expect(classification(finding)).toBe('Unavailable');expect(tone(finding)).toBe('unavailable');expect(finding.result).toBeNull()});
 it('distinguishes a provenance relationship from missing credentials',()=>{const finding=findingSchema.parse({schema_version:'1.1',finding_id:'F-rel',run_id:'RUN-rel',evidence_id:'E-1',category:'provenance',execution_status:'completed',result:'inconclusive',observation:'Measured relationship',method:'visual comparison',method_version:'1',scope:'pair',score:null,location:null,support_refs:['REL-1'],limitations:['Does not establish creation order.'],review_status:'unreviewed',error:null,details:{kind:'provenance',manifest:'not_assessed',content_binding:'not_assessed',signature:'not_assessed',signer_trust:'not_assessed',relationship:'candidate'},fixture:false});expect(classification(finding)).toBe('Relationship candidate')});
 it('labels every score raw and uncalibrated',async()=>{const fixture=await loadFixturePayload();fixture.findings.filter(f=>f.score).forEach(f=>{expect(f.score!.calibration_status).toBe('Not calibrated');expect(f.score!.interpretation).toBe('Raw model score')})});
});
