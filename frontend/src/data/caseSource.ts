import {
  ApiCase,
  ApiCaseDetail,
  ApiEvidence,
  apiCaseDetailSchema,
  apiCaseListSchema,
  apiCaseSchema,
  apiEvidenceListSchema,
  apiEvidenceSchema,
  apiHealthSchema,
  CaseRecord,
} from '../model';

export type EvidenceRegistration={
  evidence_id?:string;
  filename:string;
  media_type:'image'|'audio'|'video';
  role:'Evidence'|'Reference'|'Control';
  size_bytes:number;
  sha256:string;
};

export type CaseListQuery={q?:string;status?:string;limit?:number;offset?:number};
export type BackendHealth={connected:boolean;caseStoreReady:boolean;message:string};

export interface CaseSource{
  readonly mode:'api'|'local';
  listCases(query?:CaseListQuery):Promise<CaseRecord[]>;
  getCase(caseId:string):Promise<CaseRecord>;
  createCase(input:{title:string;description?:string},analystName?:string):Promise<CaseRecord>;
  listEvidence(caseId:string):Promise<ApiEvidence[]>;
  registerEvidence(caseId:string,input:EvidenceRegistration,analystName?:string):Promise<ApiEvidence>;
  health():Promise<BackendHealth>;
}

export class CaseSourceError extends Error{
  constructor(message:string,readonly status?:number){super(message);this.name='CaseSourceError'}
}

export function formatCaseDate(value:string):string{
  return new Intl.DateTimeFormat(undefined,{day:'2-digit',month:'short',year:'numeric'}).format(new Date(value));
}

function mapCase(value:ApiCase|ApiCaseDetail):CaseRecord{
  return {id:value.id,title:value.title,description:value.description,status:value.status,created:formatCaseDate(value.created_at),createdAt:value.created_at,createdBy:value.created_by,createdByVerified:false,evidenceCount:'evidence_count' in value?value.evidence_count:undefined};
}

async function responseMessage(response:Response):Promise<string>{
  try{
    const body=await response.json() as {detail?:unknown};
    if(typeof body.detail==='string')return body.detail;
    if(Array.isArray(body.detail))return body.detail.map(item=>typeof item==='object'&&item&&'msg' in item?String(item.msg):String(item)).join('; ');
  }catch{return `Request failed with status ${response.status}`}
  return `Request failed with status ${response.status}`;
}

export function createApiCaseSource(baseUrl:string,fetchImpl:typeof fetch=fetch):CaseSource{
  const root=baseUrl.replace(/\/$/,'');
  async function request(path:string,init?:RequestInit):Promise<unknown>{
    let response:Response;
    try{response=await fetchImpl(`${root}${path}`,init)}catch(error){throw new CaseSourceError(error instanceof Error?`Backend unavailable: ${error.message}`:'Backend unavailable')}
    if(!response.ok)throw new CaseSourceError(await responseMessage(response),response.status);
    return response.json();
  }
  return {
    mode:'api',
    async listCases(query={}){
      const parameters=new URLSearchParams();
      if(query.q)parameters.set('q',query.q);if(query.status)parameters.set('status',query.status);
      if(query.limit!==undefined)parameters.set('limit',String(query.limit));if(query.offset!==undefined)parameters.set('offset',String(query.offset));
      const suffix=parameters.size?`?${parameters}`:'';
      return apiCaseListSchema.parse(await request(`/api/cases${suffix}`)).items.map(mapCase);
    },
    async getCase(caseId){return mapCase(apiCaseDetailSchema.parse(await request(`/api/cases/${encodeURIComponent(caseId)}`)))},
    async createCase(input,analystName='Demo analyst'){
      const body=apiCaseSchema.parse(await request('/api/cases',{method:'POST',headers:{'Content-Type':'application/json','X-Analyst-Name':analystName},body:JSON.stringify(input)}));
      return mapCase(body);
    },
    async listEvidence(caseId){return apiEvidenceListSchema.parse(await request(`/api/cases/${encodeURIComponent(caseId)}/evidence`)).items},
    async registerEvidence(caseId,input,analystName='Demo analyst'){
      return apiEvidenceSchema.parse(await request(`/api/cases/${encodeURIComponent(caseId)}/evidence`,{method:'POST',headers:{'Content-Type':'application/json','X-Analyst-Name':analystName},body:JSON.stringify(input)}));
    },
    async health(){
      const health=apiHealthSchema.parse(await request('/api/health'));
      return {connected:true,caseStoreReady:health.case_store_ready,message:health.case_store_ready?'Connected · persistent case store ready':'Connected · case store unavailable'};
    },
  };
}

function createMemoryStorage():Storage{
  const values=new Map<string,string>();
  return {get length(){return values.size},clear:()=>values.clear(),getItem:key=>values.get(key)??null,key:index=>Array.from(values.keys())[index]??null,removeItem:key=>values.delete(key),setItem:(key,value)=>values.set(key,value)};
}

export function createLocalCaseSource(storage:Storage=typeof localStorage==='undefined'?createMemoryStorage():localStorage):CaseSource{
  const read=():CaseRecord[]=>{try{return JSON.parse(storage.getItem('pratyaksh-cases')||'[]') as CaseRecord[]}catch{return []}};
  const write=(cases:CaseRecord[])=>storage.setItem('pratyaksh-cases',JSON.stringify(cases));
  return {
    mode:'local',
    async listCases(){return read()},
    async getCase(caseId){const record=read().find(item=>item.id===caseId);if(!record)throw new CaseSourceError(`Case '${caseId}' was not found`,404);return record},
    async createCase(input){const id=`CASE-${new Date().getFullYear()}-${String(Date.now()).slice(-6)}`;const record={id,title:input.title.trim(),description:input.description?.trim()||'',status:'Open',created:formatCaseDate(new Date().toISOString()),createdBy:'Demo analyst',createdByVerified:false as const};write([record,...read()]);return record},
    async listEvidence(){return []},
    async registerEvidence(caseId,input){return apiEvidenceSchema.parse({case_id:caseId,evidence_id:input.evidence_id||`${caseId}-LOCAL-${Date.now()}`,filename:input.filename,media_type:input.media_type,role:input.role,size_bytes:input.size_bytes,sha256:input.sha256,hash_source:'client_declared',registered_at:new Date().toISOString(),registered_by:'Demo analyst',registered_by_verified:false,preserved:false,preserved_evidence_id:null,duplicate_hash_of:[]})},
    async health(){return {connected:false,caseStoreReady:false,message:'Local prototype · backend not configured'}},
  };
}

export const apiBaseUrl=import.meta.env.VITE_API_BASE_URL?.trim()||'';
export const caseSource:CaseSource=apiBaseUrl?createApiCaseSource(apiBaseUrl):createLocalCaseSource();
