import {describe,expect,it} from 'vitest';
import {filterAndSortCases} from './caseSource';
import {CaseRecord} from '../model';

const cases:CaseRecord[]=[
  {id:'CASE-2',title:'Zulu',description:'',status:'Open',created:'2026-10-30T10:00:00Z'},
  {id:'CASE-1',title:'Alpha',description:'',status:'Closed',created:'2026-10-29T10:00:00Z'},
];

describe('case list filtering and sorting',()=>{
  it('searches IDs and titles',()=>expect(filterAndSortCases(cases,'alpha','All','newest').map(c=>c.id)).toEqual(['CASE-1']));
  it('filters status',()=>expect(filterAndSortCases(cases,'','Open','newest').map(c=>c.id)).toEqual(['CASE-2']));
  it('sorts newest first by default choice',()=>expect(filterAndSortCases(cases,'','All','newest').map(c=>c.id)).toEqual(['CASE-2','CASE-1']));
  it('sorts by title',()=>expect(filterAndSortCases(cases,'','All','title').map(c=>c.title)).toEqual(['Alpha','Zulu']));
});
