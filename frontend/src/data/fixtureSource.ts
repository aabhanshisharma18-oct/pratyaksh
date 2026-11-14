import type {CaseRecord,Evidence,Finding} from '../model';
import type {RunRecord} from '../runs/types';
export type DevelopmentFixtures={cases:CaseRecord[];evidence:Evidence[];runs:RunRecord[];findings:Finding[]};
export const shouldLoadDevelopmentFixtures=(enabled:boolean,apiMode:boolean)=>enabled&&!apiMode;
export async function loadDevelopmentFixtures():Promise<DevelopmentFixtures|null>{
 if(import.meta.env.VITE_DEV_FIXTURE!=='true'||Boolean(import.meta.env.VITE_API_BASE_URL))return null;
 const module=await import('./fixturePayload');
 return module.loadFixturePayload();
}
