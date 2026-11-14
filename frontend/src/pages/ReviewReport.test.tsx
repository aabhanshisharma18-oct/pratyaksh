import {renderToStaticMarkup} from 'react-dom/server';
import {describe,expect,it} from 'vitest';
import type {CaseRecord,Finding} from '../model';
import {ReviewReport} from './ReviewReport';

const caseRecord:CaseRecord={id:'CASE-1',title:'Review case',description:'',status:'Open',created:'today'};
const finding:Finding={schema_version:'1.1',finding_id:'F-1',run_id:'R-1',evidence_id:'E-1',category:'tampering',execution_status:'completed',result:'inconclusive',observation:'A bounded signal was recorded.',method:'Method',method_version:'1',scope:'region',score:null,location:null,support_refs:[],limitations:['Not proof of manipulation.'],review_status:'unreviewed',error:null,details:null,fixture:true};

describe('Review & Report workflow',()=>{
 it('renders referenced summary chips and keeps report generation gated',()=>{const markup=renderToStaticMarkup(<ReviewReport caseRecord={caseRecord} findings={[finding]} evidence={[]} notes={[]} onOpenFinding={()=>{}} onReview={()=>{}}/>);expect(markup).toContain('E-1');expect(markup).toContain('F-1');expect(markup).toContain('Generate report');expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>.*Generate report/s);expect(markup.toLowerCase()).not.toContain('definitely fake')});
});
