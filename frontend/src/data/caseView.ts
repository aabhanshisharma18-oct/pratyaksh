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
  return items.filter(item=>(item.fixture&&caseId==='CASE-2026-014')||(!item.fixture&&item.id.startsWith(caseId)));
}

export type CaseSort='newest'|'oldest'|'title';
export function filterAndSortCases(cases:CaseRecord[],query:string,status:string,sort:CaseSort):CaseRecord[]{
  const term=query.trim().toLocaleLowerCase();
  const filtered=cases.filter(item=>(status==='All'||item.status===status)&&(!term||item.id.toLocaleLowerCase().includes(term)||item.title.toLocaleLowerCase().includes(term)));
  return [...filtered].sort((a,b)=>{
    if(sort==='title')return a.title.localeCompare(b.title);
    const delta=Date.parse(b.created)-Date.parse(a.created);
    return sort==='newest'?delta:-delta;
  });
}
