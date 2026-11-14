import {describe,expect,it} from 'vitest';
import type {Finding,Note} from '../model';
import {buildReferencedSummary,reportGate,summaryTextIsAllowed,validateSummaryReferences} from './summaryPolicy';

const finding:Finding={schema_version:'1.1',finding_id:'F-1',run_id:'R-1',evidence_id:'E-1',category:'synthetic_media',execution_status:'completed',result:'indicators_detected',observation:'A bounded signal was recorded.',method:'Detector',method_version:'1',scope:'one face',score:{value:.7,range:[0,1],positive_class:'signal',interpretation:'raw score',calibration_status:'not calibrated'},location:{kind:'time_range',start_ms:12000,end_ms:18000},support_refs:[],limitations:['Not proof of manipulation.'],review_status:'unreviewed',error:null,details:null,fixture:true};

describe('referenced summary policy',()=>{
 it('keeps every statement linked to an existing finding',()=>{const summary=buildReferencedSummary([finding]);expect(validateSummaryReferences(summary,[finding])).toEqual(summary);expect(validateSummaryReferences([{...summary[0],reference:{...summary[0].reference,findingId:'missing'}}],[finding])).toEqual([])});
 it('blocks forbidden conclusions',()=>{for(const text of ['definitely fake','This file is authentic','proven manipulated'])expect(summaryTextIsAllowed(text)).toBe(false);expect(summaryTextIsAllowed('Indicators were recorded in the examined scope.')).toBe(true)});
 it('keeps report generation disabled until findings are reviewed and summary approved',()=>{expect(reportGate([finding],[],true).ready).toBe(false);const note:Note={id:'N-1',findingId:'F-1',text:'Reviewed',status:'reviewed',at:'2026-01-01T00:00:00Z',author:'Analyst',authorVerified:false};expect(reportGate([finding],[note],false).ready).toBe(false);expect(reportGate([finding],[note],true).ready).toBe(true)});
});
