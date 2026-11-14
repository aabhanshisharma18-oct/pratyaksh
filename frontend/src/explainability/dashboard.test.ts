import {describe,expect,it} from 'vitest';
import {loadFixturePayload} from '../data/fixturePayload';
import {explainFinding,summarizeExplainability} from './dashboard';
describe('explainability dashboard',()=>{
 it('summarizes conservative states without creating a verdict',async()=>{const fixture=await loadFixturePayload(),summary=summarizeExplainability(fixture.findings);expect(summary.total).toBe(fixture.findings.length);expect(summary.completed).toBeLessThan(summary.total);expect(summary.unavailable).toBeGreaterThan(0)});
 it('uses recorded method, scope, score and limitations',async()=>{const fixture=await loadFixturePayload(),finding=fixture.findings.find(item=>item.score?.value!=null)!;const record=explainFinding(finding,fixture.evidence.find(item=>item.id===finding.evidence_id),fixture.runs.find(item=>item.run_id===finding.run_id));expect(record.basis.join(' ')).toContain(finding.method);expect(record.basis.join(' ')).toContain(finding.scope);expect(record.unknowns).toEqual(expect.arrayContaining(finding.limitations))});
 it('does not present an uncalibrated signal as confidence',async()=>{const fixture=await loadFixturePayload(),finding=fixture.findings.find(item=>item.score)!;const record=explainFinding(finding);expect(record.scoreMeaning.toLowerCase()).not.toContain('confidence');expect(record.scorePercent).not.toBeNull()});
});
