import {describe,it,expect} from 'vitest';
import {caseOverviewStatus} from './CaseStatusOverview';
describe('case overview status',()=>{
 it('keeps cases without findings or saved reports pending',()=>expect(caseOverviewStatus(false,false)).toBe('pending'));
 it('counts recorded findings for review without claiming completion',()=>expect(caseOverviewStatus(true,false)).toBe('review'));
 it('identifies an existing saved report independently of findings',()=>{
  expect(caseOverviewStatus(false,true)).toBe('reported');
  expect(caseOverviewStatus(true,true)).toBe('reported');
 });
});
