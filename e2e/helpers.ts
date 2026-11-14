import {expect,type APIRequestContext,type Page} from '@playwright/test';
import {createHash,randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export const api='http://127.0.0.1:18000';
const here=path.dirname(fileURLToPath(import.meta.url));
export const fixture=(name:string)=>path.join(here,'fixtures',name);
export const unique=(prefix:string)=>`${prefix}-${randomUUID().slice(0,8)}`;

export async function createCase(request:APIRequestContext,title=unique('D4 case')){
 const response=await request.post(`${api}/api/cases`,{data:{title,description:'Created by Playwright D4 E2E'}});
 expect(response.ok(),await response.text()).toBeTruthy();return response.json() as Promise<{id:string;title:string}>;
}
export async function registerAndRun(request:APIRequestContext,caseId:string,fileName:string,mediaType:'image'|'audio'|'video',filePath:string){
 const bytes=await fs.readFile(filePath),evidenceId=unique('EVID');
 let response=await request.post(`${api}/api/cases/${caseId}/evidence`,{data:{evidence_id:evidenceId,filename:fileName,media_type:mediaType,role:'Evidence',size_bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}});
 expect(response.ok(),await response.text()).toBeTruthy();
 response=await request.post(`${api}/api/evidence/${evidenceId}/runs`,{multipart:{case_id:caseId,file:{name:fileName,mimeType:mediaType==='image'?'image/png':mediaType==='audio'?'audio/wav':'video/mp4',buffer:bytes}}});
 expect(response.ok(),await response.text()).toBeTruthy();const run=await response.json();
 await expect.poll(async()=>request.get(`${api}/api/runs/${run.run_id}`).then(r=>r.json()).then(value=>value.execution_status),{timeout:15_000}).toMatch(/completed|partial|failed/);
 const terminal=await request.get(`${api}/api/runs/${run.run_id}`).then(r=>r.json());return {evidenceId,runId:run.run_id,run:terminal};
}
export async function createCaseUi(page:Page,title=unique('D4 UI case')){
 await page.goto('/#/cases',{waitUntil:'domcontentloaded'});await page.getByRole('button',{name:/New case|Create your first case/}).first().click();
 await page.getByLabel('Case title').fill(title);await page.getByLabel('Case context').fill('Playwright full-stack case');
 await page.getByRole('button',{name:'Create case'}).click();await expect(page.getByRole('heading',{name:title})).toBeVisible();return title;
}
export async function uploadUi(page:Page,filePath:string){
 await page.getByRole('button',{name:'Add evidence'}).first().click();await page.locator('input[type=file]').setInputFiles(filePath);
 await page.getByRole('button',{name:/Preserve evidence|Calculate SHA-256 & register inventory/}).click();
 await page.getByRole('button',{name:/Open .+/}).first().click();
 await expect(page.getByRole('button',{name:'Run analysis'})).toBeEnabled();
}
export async function runUi(page:Page){
 await page.getByRole('button',{name:'Run analysis'}).click();
 await expect(page.locator('.run-status').filter({hasText:/Completed|Partial|Failed/}).first()).toBeVisible({timeout:15_000});
}
