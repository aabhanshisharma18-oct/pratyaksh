import {z} from 'zod';
import {findingSchema,type Finding,type Note} from '../model';

const noteSchema=z.object({note_id:z.string(),finding_id:z.string(),finding_sha256:z.string().regex(/^[0-9a-f]{64}$/),status:z.enum(['reviewed','questioned']),text:z.string(),author:z.string(),author_verified:z.literal(false),created_at:z.string().datetime({offset:true})}).strict();
const noteListSchema=z.object({items:z.array(noteSchema),total:z.number().int().nonnegative()}).strict();
const findingResponseSchema=z.object({finding_id:z.string(),evidence_id:z.string(),run_id:z.string(),case_id:z.string().nullable(),recorded_at:z.string().datetime({offset:true}),finding_sha256:z.string().regex(/^[0-9a-f]{64}$/),finding:z.record(z.string(),z.unknown())}).strict();
const findingListSchema=z.object({items:z.array(findingResponseSchema),total:z.number().int().nonnegative()}).strict();

export class ReviewApiError extends Error{constructor(message:string,readonly status?:number){super(message);this.name='ReviewApiError'}}
const toNote=(value:z.infer<typeof noteSchema>):Note=>({id:value.note_id,findingId:value.finding_id,text:value.text,status:value.status,at:value.created_at,author:value.author,authorVerified:false});
async function message(response:Response){try{const body=await response.json() as {detail?:unknown};return typeof body.detail==='string'?body.detail:`Request failed with status ${response.status}`}catch{return `Request failed with status ${response.status}`}}

export function createReviewApi(baseUrl:string,fetchImpl:typeof fetch=globalThis.fetch.bind(globalThis) as typeof fetch){
 const root=baseUrl.replace(/\/$/,'');
 async function request(path:string,init?:RequestInit){let response:Response;try{response=await fetchImpl(`${root}${path}`,init)}catch(error){throw new ReviewApiError(error instanceof Error?error.message:'Review service unavailable')}if(!response.ok)throw new ReviewApiError(await message(response),response.status);return response.json()}
 return {
  async registerFinding(caseId:string|undefined,finding:Finding,signal?:AbortSignal){return findingResponseSchema.parse(await request('/api/findings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:caseId||null,finding}),signal}))},
  async listFindings(caseId:string,signal?:AbortSignal){return findingListSchema.parse(await request(`/api/findings?case_id=${encodeURIComponent(caseId)}`,{signal})).items.map(item=>findingSchema.parse(item.finding))},
  async listNotes(findingId:string,signal?:AbortSignal){const value=noteListSchema.parse(await request(`/api/findings/${encodeURIComponent(findingId)}/notes`,{signal}));return value.items.map(toNote)},
  async createNote(findingId:string,input:{status:'reviewed'|'questioned';text:string},analyst='Demo analyst',signal?:AbortSignal){return toNote(noteSchema.parse(await request(`/api/findings/${encodeURIComponent(findingId)}/notes`,{method:'POST',headers:{'Content-Type':'application/json','X-Analyst-Name':analyst},body:JSON.stringify(input),signal})))},
 };
}
