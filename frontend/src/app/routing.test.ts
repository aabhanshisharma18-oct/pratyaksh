import {describe,expect,it} from 'vitest';
import {hasKnownCase,parseHash,routeFor} from './routing';

describe('hash routing',()=>{
  it('parses case and evidence routes',()=>{
    expect(parseHash('#/cases/CASE-1')).toMatchObject({page:'Overview',caseId:'CASE-1'});
    expect(parseHash('#/cases/CASE-1/evidence/EVID-2?tab=provenance')).toMatchObject({page:'Workbench',caseId:'CASE-1',evidenceId:'EVID-2',tab:'provenance'});
  });
  it('returns not found for unknown routes',()=>expect(parseHash('#/unknown')).toMatchObject({page:'NotFound'}));
  it('identifies an unknown case route',()=>expect(hasKnownCase(parseHash('#/cases/MISSING'),['CASE-1'])).toBe(false));
  it('builds report links',()=>expect(routeFor('Reports','CASE-1')).toBe('/cases/CASE-1/reports'));
});
