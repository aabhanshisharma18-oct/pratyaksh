import {describe,expect,it} from 'vitest';
import {savedSections,sectionHeading} from './sections';

describe('saved report section presentation',()=>{
 it('shows every section for historical revisions without a section field',()=>{
  expect(savedSections()).toEqual(['methods','evidence','findings','coverage','notes','limitations']);
 });
 it('numbers selected sections continuously in document order',()=>{
  const selected=savedSections(['limitations','coverage','methods','findings']);
  expect(sectionHeading('findings',selected)).toBe('2. Forensic findings');
  expect(sectionHeading('limitations',selected)).toBe('4. Limitations');
 });
});
