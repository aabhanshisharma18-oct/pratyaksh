import {describe,expect,it} from 'vitest';
import {linkedFindingForSample} from './MediaTimeline';
import {emptySelection,selectionReducer} from '../../viewer/selection';
import type {TimeMarker} from '../../viewer/markers';

describe('video finding and sample timeline links',()=>{
 const marker:TimeMarker={findingId:'F-1',positionMs:2500,interval:null,tone:'warning'};
 it('links a selected timeline sample to its finding',()=>expect(linkedFindingForSample([marker],2500)?.findingId).toBe('F-1'));
 it('links a selected finding back to its timeline timestamp',()=>{const selected=selectionReducer(emptySelection,{type:'finding',findingId:marker.findingId,positionMs:marker.positionMs,interval:marker.interval,durationMs:10000});expect(selected).toMatchObject({findingId:'F-1',positionMs:2500})});
});
