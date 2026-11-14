import {test,expect,type APIRequestContext,type Page} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash,randomUUID} from 'node:crypto';
import {deflateSync} from 'node:zlib';

const api='http://127.0.0.1:18112';
const here=path.dirname(fileURLToPath(import.meta.url));
async function createCase(request:APIRequestContext){
 const response=await request.post(api+'/api/cases',{data:{title:'Briefing test '+randomUUID().slice(0,8)}});
 expect(response.ok(),await response.text()).toBeTruthy();return response.json();
}
async function voiceRun(request:APIRequestContext,caseId:string){
 const bytes=await fs.readFile(path.join(here,'fixtures/valid.wav'));
 const evidenceId='EVID-'+randomUUID();
 const registered=await request.post(`${api}/api/cases/${caseId}/evidence`,{data:{evidence_id:evidenceId,filename:'voice.wav',media_type:'audio',role:'Evidence',size_bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}});
 expect(registered.ok(),await registered.text()).toBeTruthy();
 const queued=await request.post(`${api}/api/evidence/${evidenceId}/runs`,{multipart:{case_id:caseId,file:{name:'inconclusive.wav',mimeType:'audio/wav',buffer:bytes}}});
 expect(queued.ok(),await queued.text()).toBeTruthy();const queuedRun=await queued.json();
 await expect.poll(()=>request.get(`${api}/api/runs/${queuedRun.run_id}`).then(r=>r.json()).then(r=>r.execution_status)).toMatch(/completed|partial|failed/);
 const run=await request.get(`${api}/api/runs/${queuedRun.run_id}`).then(r=>r.json());
 return {run,evidenceId,finding:run.findings[0]};
}
async function openDashboard(page:Page,caseId:string){
 await page.goto(`/#/cases/${caseId}`);
 await page.getByRole('heading',{name:/Briefing test/}).waitFor();
 await page.goto(`/#/cases/${caseId}/review`);
 await expect(page.getByRole('heading',{name:'Explain this case',exact:true})).toBeVisible();
 await expect(page).toHaveURL(new RegExp(`/cases/${caseId}/review`));
}
function brief(caseId:string,source:Record<string,unknown>){
 const item={text:'Review the recorded observation.',basis:'This is an existing examination record.',source_ids:['S1']};
 return {case_id:caseId,snapshot_sha256:'test-only-snapshot',generated_at:new Date().toISOString(),model:'test-provider',cached:false,
  sources:[{source_id:'S1',limitations:['The available evidence does not establish authenticity.'],...source}],
  key_findings:[item],open_questions:[item],next_steps:[item],cautions:[{text:'The recorded result is inconclusive.',source_ids:['S1']}]};
}

test('missing backend key shows an actionable error while recorded findings remain usable',async({page,request})=>{
 const c=await createCase(request),{finding}=await voiceRun(request,c.id);
 await openDashboard(page,c.id);
 await page.getByRole('button',{name:'Explain this case',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('PRUNE_API_KEY');
 await expect(page.locator('.review-findings article').filter({hasText:finding.finding_id})).toBeVisible();
 await expect(page.locator('.case-briefing-sections')).toHaveCount(0);
});

test('three-section briefing links a voice statement to the exact saved finding and remains usable on mobile',async({page,request},testInfo)=>{
 const c=await createCase(request),{finding,evidenceId,run}=await voiceRun(request,c.id);
 await page.route(`**/api/cases/${c.id}/briefing`,route=>route.fulfill({json:brief(c.id,{kind:'finding',evidence_ids:[evidenceId],media_types:['audio'],finding_id:finding.finding_id,run_id:run.run_id,observation:finding.observation,execution_status:'completed',result:'inconclusive'})}));
 await openDashboard(page,c.id);
 await page.getByRole('button',{name:'Explain this case',exact:true}).click();
 for(const name of ['Key findings','Open questions','Suggested next steps'])await expect(page.locator('.case-briefing').getByRole('heading',{name,exact:true})).toBeVisible();
 await expect(page.getByText('The recorded result is inconclusive.',{exact:true})).toBeVisible();
 await page.screenshot({path:testInfo.outputPath('case-briefing-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBeTruthy();
 await page.screenshot({path:testInfo.outputPath('case-briefing-mobile.png'),fullPage:true});
 await page.getByRole('link',{name:/Open the voice scan/}).first().click();
 await expect(page).toHaveURL(new RegExp(`/evidence/${evidenceId}\\?tab=viewer&finding=${finding.finding_id}&run=${run.run_id}`));
 await expect(page.locator('.viewer-header')).toContainText('voice.wav');
 await expect(page.locator('.explain-finding-card').filter({hasText:finding.finding_id})).toBeVisible();
});

// Generate reproducible non-private textured PNGs without another image dependency.
function imagePng(crop=false){
 const fullWidth=400,fullHeight=300,width=crop?300:fullWidth,height=crop?230:fullHeight;
 const raw=Buffer.alloc((width*3+1)*height);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const px=x+(crop?45:0),py=y+(crop?30:0);
  let seed=(px*374761393+py*668265263)>>>0;seed=Math.imul(seed^(seed>>>13),1274126177)>>>0;
  const color=((px%60)<5||(py%50)<5)?245:((seed>>>24)*.8+20)|0;
  const at=y*(width*3+1)+1+x*3;raw[at]=color;raw[at+1]=color;raw[at+2]=color;
 }
 function chunk(type:string,data:Buffer){
  const name=Buffer.from(type),body=Buffer.concat([name,data]);let crc=0xffffffff;
  for(const byte of body){crc^=byte;for(let bit=0;bit<8;bit++)crc=(crc>>>1)^((crc&1)?0xedb88320:0)}
  const size=Buffer.alloc(4),hash=Buffer.alloc(4);size.writeUInt32BE(data.length);hash.writeUInt32BE((crc^0xffffffff)>>>0);
  return Buffer.concat([size,body,hash]);
 }
 const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=2;
 return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
}

test('comparison citation opens the saved report, correct image pair and highlighted matching regions',async({page,request})=>{
 const c=await createCase(request),ids:string[]=[];
 for(const crop of [false,true]){
  const response=await request.post(`${api}/api/cases/${c.id}/originals`,{multipart:{file:{name:crop?'crop.png':'base.png',mimeType:'image/png',buffer:imagePng(crop)}}});
  expect(response.ok(),await response.text()).toBeTruthy();ids.push((await response.json()).evidence_id);
 }
 const compared=await request.post(`${api}/api/d1/provenance/cases/${c.id}/analyze`,{data:{evidence_ids:ids}});
 expect(compared.ok(),await compared.text()).toBeTruthy();const report=await compared.json();
 const edge=report.relationships.find((item:{kind:string})=>item.kind==='matching_content');
 expect(edge,'Synthetic crop should create a recorded geometric relationship').toBeTruthy();
 await page.route(`**/api/cases/${c.id}/briefing`,route=>route.fulfill({json:brief(c.id,{kind:'relationship',evidence_ids:ids,media_types:['image','image'],analysis_id:report.analysis_id,relationship_id:edge.id,observation:'Aligned visual regions were recorded.',execution_status:'completed',result:'relationship_recorded'})}));
 await openDashboard(page,c.id);await page.getByRole('button',{name:'Explain this case',exact:true}).click();
 await page.getByRole('link',{name:/View the comparison/}).first().click();
 await expect(page).toHaveURL(new RegExp(`analysis=${report.analysis_id}&relationship=${edge.id}`));
 const comparison=page.locator('#provenance-comparison');
 await expect(comparison).toBeVisible();await expect(comparison.locator('figure')).toHaveCount(2);
 await expect(comparison.locator('figcaption').filter({hasText:'base.png'})).toBeVisible();
 await expect(comparison.locator('figcaption').filter({hasText:'crop.png'})).toBeVisible();
 await expect(comparison.locator('.provenance-match-region')).toHaveCount(2);
 await expect(comparison.getByRole('checkbox',{name:'Show matching points and regions'})).toBeChecked();
});
