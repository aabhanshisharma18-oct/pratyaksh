import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe,expect,it} from 'vitest';
import {FindingTechnicalDetails} from './FindingTechnicalDetails';
import type {Finding} from '../model';

describe('saved finding settings',()=>{
 it('distinguishes recorded zero and null from absent settings',()=>{
  const finding={details:{threshold:0,trust_policy:null},location:null} as Finding;
  const markup=renderToStaticMarkup(<FindingTechnicalDetails finding={finding}/>);
  expect(markup).toContain('<code>0</code>');
  expect(markup).toContain('recorded without a value');
  expect(markup).toContain('Not recorded in saved finding');
 });
 it('escapes untrusted model and location strings',()=>{
  const finding={details:{model:'<script>alert(1)</script>'},location:{label:'<img src=x onerror=alert(1)>'}} as Finding;
  const markup=renderToStaticMarkup(<FindingTechnicalDetails finding={finding}/>);
  expect(markup).not.toContain('<script>');
  expect(markup).not.toContain('<img');
  expect(markup).toContain('&lt;script&gt;');
 });
});
