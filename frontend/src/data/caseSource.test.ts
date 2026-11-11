import {beforeEach,describe,expect,it,vi} from 'vitest';
import {apiCaseSchema,apiEvidenceSchema} from '../model';
import {CaseSourceError,createApiCaseSource} from './caseSource';

const caseBody={id:'CASE-2026-000001',title:'Persistent case',description:'Context',status:'Open',created_at:'2026-11-11T04:00:00Z',created_by:'Aadya',created_by_verified:false as const};
const evidenceBody={case_id:caseBody.id,evidence_id:'EVID-1',filename:'sample.png',media_type:'image' as const,role:'Evidence' as const,size_bytes:12,sha256:'a'.repeat(64),hash_source:'client_declared' as const,registered_at:'2026-11-11T04:01:00Z',registered_by:'Aadya',registered_by_verified:false as const,preserved:false as const,preserved_evidence_id:null,duplicate_hash_of:[]};

describe('case API schemas',()=>{
  it('accepts honest case and inventory responses',()=>{expect(apiCaseSchema.parse(caseBody).id).toBe(caseBody.id);expect(apiEvidenceSchema.parse(evidenceBody).preserved).toBe(false)});
  it('rejects preservation and verified-identity overclaims',()=>{expect(apiEvidenceSchema.safeParse({...evidenceBody,preserved:true}).success).toBe(false);expect(apiCaseSchema.safeParse({...caseBody,created_by_verified:true}).success).toBe(false)});
});

describe('apiCaseSource',()=>{
  beforeEach(()=>vi.restoreAllMocks());
  it('loads and maps server cases',async()=>{
    const fetcher=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>new Response(JSON.stringify({items:[caseBody],total:1,limit:50,offset:0}),{status:200,headers:{'Content-Type':'application/json'}}));
    const source=createApiCaseSource('http://127.0.0.1:8000',fetcher as typeof fetch);
    const cases=await source.listCases();
    expect(cases[0]).toMatchObject({id:caseBody.id,title:'Persistent case',createdBy:'Aadya'});
    expect(fetcher).toHaveBeenCalledOnce();
  });
  it('creates a case using the server-issued ID',async()=>{
    const fetcher=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>new Response(JSON.stringify(caseBody),{status:201,headers:{'Content-Type':'application/json'}}));
    const record=await createApiCaseSource('http://api.test/',fetcher as typeof fetch).createCase({title:'Persistent case'},'Aadya');
    expect(record.id).toBe('CASE-2026-000001');
    expect(fetcher.mock.calls[0][0]).toBe('http://api.test/api/cases');
  });
  it('surfaces a 404 without falling back',async()=>{
    const fetcher=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>new Response(JSON.stringify({detail:"Case 'missing' was not found"}),{status:404,headers:{'Content-Type':'application/json'}}));
    await expect(createApiCaseSource('http://api.test',fetcher as typeof fetch).getCase('missing')).rejects.toMatchObject({status:404});
  });
  it('surfaces network errors without a local request',async()=>{
    const fetcher=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>{throw new TypeError('connection refused')});
    await expect(createApiCaseSource('http://api.test',fetcher as typeof fetch).listCases()).rejects.toBeInstanceOf(CaseSourceError);
    expect(fetcher).toHaveBeenCalledOnce();
  });
});
