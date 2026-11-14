import {describe,expect,it} from 'vitest';
import {hasKnownCase,parseHash,routeFor} from './routing';

describe('hash routing',()=>{
  it('parses case and evidence routes',()=>{
    expect(parseHash('#/cases/CASE-1')).toMatchObject({page:'Overview',caseId:'CASE-1'});
    expect(parseHash('#/cases/CASE-1/audit?type=run.failed')).toMatchObject({page:'Audit',caseId:'CASE-1'});
    expect(parseHash('#/cases/CASE-1/evidence/EVID-2?tab=provenance')).toMatchObject({page:'Workbench',caseId:'CASE-1',evidenceId:'EVID-2',tab:'provenance'});
  });
  it('opens each consolidated workflow without a case',()=>{
    expect(parseHash('#/analysis').page).toBe('MediaAnalysis');
    expect(parseHash('#/provenance').page).toBe('Provenance');
    expect(parseHash('#/review').page).toBe('ReviewReport');
    expect(routeFor('ReviewReport')).toBe('/review');
    expect(routeFor('Provenance')).toBe('/provenance');
    expect(routeFor('Provenance','CASE-1')).toBe('/cases/CASE-1/provenance');
    expect(routeFor('MediaAnalysis')).toBe('/analysis');
  });
  it('redirects old workflow routes without breaking links',()=>{
    expect(parseHash('#/detection')).toMatchObject({page:'MediaAnalysis',redirectTo:'/analysis'});
    expect(parseHash('#/authentication')).toMatchObject({page:'MediaAnalysis',redirectTo:'/analysis'});
    expect(parseHash('#/explainability')).toMatchObject({page:'ReviewReport',redirectTo:'/review'});
    expect(parseHash('#/reports')).toMatchObject({page:'ReviewReport',redirectTo:'/review'});
    expect(parseHash('#/cases/CASE-1/reports')).toMatchObject({page:'ReviewReport',redirectTo:'/cases/CASE-1/review'});
  });
  it('returns not found for unknown routes',()=>expect(parseHash('#/unknown')).toMatchObject({page:'NotFound'}));
  it('identifies an unknown case route',()=>expect(hasKnownCase(parseHash('#/cases/MISSING'),['CASE-1'])).toBe(false));
  it('builds consolidated case workflow links',()=>{expect(routeFor('MediaAnalysis','CASE-1')).toBe('/cases/CASE-1/analysis');expect(routeFor('ReviewReport','CASE-1')).toBe('/cases/CASE-1/review')});
  it('builds case activity links',()=>expect(routeFor('Audit','CASE-1')).toBe('/cases/CASE-1/audit'));
  it('parses viewer selection without trusting bad values',()=>{expect(parseHash('#/cases/C/evidence/E?t=12.4&start=1&end=2')).toMatchObject({positionMs:12400,startMs:1000,endMs:2000});expect(parseHash('#/cases/C/evidence/E?t=bad&start=4&end=2')).not.toHaveProperty('positionMs')});
  it('round-trips finding, run and layer state without breaking existing params',()=>{const path=routeFor('Workbench','CASE-1','EVID-2','Viewer',{findingId:'F-1',runId:'RUN-1',layer:'faces'});expect(parseHash(`#${path}&t=1`)).toMatchObject({findingId:'F-1',runId:'RUN-1',layer:'faces',positionMs:1000})});
});
