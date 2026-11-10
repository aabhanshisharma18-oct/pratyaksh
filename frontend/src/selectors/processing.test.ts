import {describe,expect,it} from 'vitest';
import {Evidence,Finding,findingSchema} from '../model';
import {selectProcessingSummary} from './processing';

const evidence:Evidence={id:'E-1',name:'x.jpg',type:'image',role:'Evidence',size:'1 KB',duration:'—',received:'2026-01-01T00:00:00Z',hash:'abc',fixture:false,status:'',dimensions:''};
const statuses=['queued','running','completed','failed','unsupported','not_applicable','cancelled'] as const;
const finding=(status:typeof statuses[number],fixture=false):Finding=>findingSchema.parse({schema_version:'1.0',finding_id:`F-${status}`,run_id:'RUN-1',evidence_id:'E-1',category:'synthetic_media',execution_status:status,result:null,observation:'Test',method:'test',method_version:'1',scope:'test',score:null,location:null,support_refs:[],limitations:[],review_status:'unreviewed',fixture});

describe('processing summary selector',()=>{
  it('counts every execution status without converting failures into clean results',()=>{
    const result=selectProcessingSummary([evidence],statuses.map(status=>finding(status)));
    expect(result.fixture).toBe(false);
    const counts=result.channels.find(channel=>channel.channel==='synthetic_media')!.counts;
    statuses.forEach(status=>expect(counts[status]).toBe(1));
  });
  it('marks empty channels and empty cases as not examined',()=>{
    expect(selectProcessingSummary([evidence],[]).channels.every(channel=>channel.counts.not_examined===1)).toBe(true);
    expect(selectProcessingSummary([],[]).lastRunId).toBeNull();
  });
  it('preserves fixture provenance',()=>expect(selectProcessingSummary([evidence],[finding('completed',true)]).fixture).toBe(true));
});
