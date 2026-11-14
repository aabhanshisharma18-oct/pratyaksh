import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe,expect,it} from 'vitest';
import sample from '../../../docs/d5/samples/live-partial-report.json';
import {savedReportSchema} from './api';
import {cellState,reportVisualModel,reportMilestones,scoreGroups,type ReportData} from './visualModel';
import {ReportVisualSummary} from './ReportVisuals';
import type {Finding} from '../model';

const base=savedReportSchema.parse({snapshot:sample,sha256:'a'.repeat(64)}).snapshot;
const finding=(change:Partial<Finding>):Finding=>({...base.findings[0].finding,execution_status:'completed',error:null,score:null,...change});
const withFindings=(findings:Finding[]):ReportData=>({...base,findings:findings.map(f=>({finding_id:f.finding_id,finding_sha256:'a'.repeat(64),finding:f}))});

describe('saved report visuals',()=>{
 it('counts evidence-channel cells rather than inflating coverage with repeated findings',()=>{
  const report=withFindings([finding({finding_id:'F-1'}),finding({finding_id:'F-2'})]);
  const model=reportVisualModel(report);
  expect(model.total).toBe(4);
  expect(model.counts.completed).toBe(1);
  expect(model.counts.not_assessed).toBe(3);
  expect(model.channelSummaries[0].count).toBe(2);
 });
 it('preserves unavailable, incomplete and missing assessments',()=>{
  expect(cellState([])).toBe('not_assessed');
  expect(cellState([finding({}),finding({execution_status:'unsupported'})])).toBe('partial');
  expect(cellState([finding({execution_status:'failed'})])).toBe('failed');
  expect(cellState([finding({execution_status:'running'}),finding({})])).toBe('running');
  expect(cellState([finding({execution_status:'not_applicable'})])).toBe('not_applicable');
 });
 it('separates score methods, runs, positive classes and ranges',()=>{
  const score={value:0.5,range:[0,1] as [number,number],positive_class:'synthetic',interpretation:'Raw score',calibration_status:'Not calibrated'};
  const report=withFindings([finding({finding_id:'F-1',score}),finding({finding_id:'F-2',method:'Other method',score}),finding({finding_id:'F-3',score:{...score,positive_class:'tampered'}})]);
  expect(scoreGroups(report,report.evidence[0].evidence_id)).toHaveLength(3);
 });
 it('keeps timestamp zero and rejects unavailable, missing or out-of-range scores',()=>{
  const score={value:0,range:[0,1] as [number,number],positive_class:'synthetic',interpretation:'Raw score',calibration_status:'Not calibrated'};
  const report=withFindings([finding({finding_id:'F-1',score,location:{kind:'point',timestamp_ms:0}}),finding({finding_id:'F-2',execution_status:'unsupported',score}),finding({finding_id:'F-3',score:{...score,value:2}})]);
  const groups=scoreGroups(report,report.evidence[0].evidence_id);
  expect(groups).toHaveLength(1);
  expect(groups[0].points).toEqual([{id:'F-1',value:0,time:0}]);
 });
 it('does not mix another evidence item into its selected score view',()=>{
  const report=withFindings([finding({evidence_id:'OTHER',score:{value:0.7,range:[0,1],positive_class:'synthetic',interpretation:'Raw',calibration_status:'No'}})]);
  expect(scoreGroups(report,report.evidence[0].evidence_id)).toEqual([]);
 });
 it('uses saved preparation and review times without manufacturing missing milestones',()=>{
  const report={...base,audit_summary:undefined};
  const rows=reportMilestones(report);
  expect(rows.map(row=>row.label)).toEqual(['Report prepared','Report reviewed']);
  expect(rows[0].time).toBe(base.prepared_at);
 });
 it('renders the same factual summary for the printable report',()=>{
  const markup=renderToStaticMarkup(<ReportVisualSummary report={base} compact/>);
  expect(markup).toContain('evidence-channel cells');
  expect(markup).toContain('Unsupported');
  expect(markup).not.toContain('authenticity score');
  expect(markup).toContain('d5-channel-card integrity');
 });
});
