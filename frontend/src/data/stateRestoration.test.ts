import {describe,expect,it} from 'vitest';import {restoreKnownId} from './stateRestoration';
describe('state restoration',()=>{it('keeps known ids and degrades stale ids to the default',()=>{expect(restoreKnownId('F-2',['F-1','F-2'],'F-1')).toBe('F-2');expect(restoreKnownId('STALE',['F-1','F-2'],'F-1')).toBe('F-1')})});
