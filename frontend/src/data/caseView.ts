import {CaseRecord,Evidence,Finding} from '../model';

export const CASES_KEY='pratyaksh-cases';
export const NOTES_KEY='pratyaksh-notes';

function read<T>(key:string,fallback:T):T{
  try{return JSON.parse(localStorage.getItem(key)||'null')??fallback}catch{return fallback}
}

export type CaseSource={
  fixture:boolean;
  getCases:()=>CaseRecord[];
  saveCases:(cases:CaseRecord[])=>void;
  getEvidence:()=>Evidence[];
  getFindings:()=>Finding[];
};

export function createCaseSource(fixture:boolean):CaseSource{
  return {
    fixture,
    getCases:()=>read(CASES_KEY,[]),
    saveCases:cases=>localStorage.setItem(CASES_KEY,JSON.stringify(cases)),
    getEvidence:()=>[],
    getFindings:()=>[],
  };
}

export function evidenceForCase(items:Evidence[],caseId:string):Evidence[]{
  return items.filter(item=>(item.fixture&&caseId==='CASE-2026-014')||(!item.fixture&&(item.caseId?item.caseId===caseId:item.id.startsWith(caseId))));
}

export type CaseSort='activity_desc'|'activity_asc'|'newest'|'oldest'|'title';
export function filterAndSortCases(cases:CaseRecord[],query:string,status:string,sort:CaseSort):CaseRecord[]{
  const term=query.trim().toLocaleLowerCase();
  const filtered=cases.filter(item=>(status==='All'||item.status===status)&&(!term||item.id.toLocaleLowerCase().includes(term)||item.title.toLocaleLowerCase().includes(term)));
  return [...filtered].sort((a,b)=>{
    if(sort==='title')return a.title.localeCompare(b.title)||a.id.localeCompare(b.id);
    const field=sort.startsWith('activity')?'lastActivityAt':'createdAt';
    const aTime=Date.parse(a[field]||a.created),bTime=Date.parse(b[field]||b.created),delta=bTime-aTime;
    const ordered=sort==='activity_desc'||sort==='newest'?delta:-delta;
    return ordered||a.id.localeCompare(b.id)*(sort==='activity_desc'||sort==='newest'?-1:1);
  });
}
