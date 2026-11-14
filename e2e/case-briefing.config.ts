import {defineConfig,devices} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const data=path.join(root,'.e2e-tmp',`case-briefing-${process.pid}`);
fs.mkdirSync(data,{recursive:true});

export default defineConfig({
 testDir:'.',testMatch:'case-briefing.spec.ts',workers:1,retries:0,timeout:60_000,
 expect:{timeout:12_000},reporter:'list',outputDir:path.join(data,'results'),
 use:{baseURL:'http://127.0.0.1:15112',screenshot:'only-on-failure'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
 webServer:[
  {command:'python -m uvicorn main:app --host 127.0.0.1 --port 18112',cwd:path.join(root,'backend'),url:'http://127.0.0.1:18112/api/health',timeout:120_000,
   env:{...process.env,PRUNE_API_KEY:'',PRATYAKSH_DB_PATH:path.join(data,'cases.db'),PRATYAKSH_PROVENANCE_DIR:path.join(data,'provenance'),PRATYAKSH_ENV:'test',PRATYAKSH_E2E_STUB:'1',PRATYAKSH_CORS_ORIGINS:'http://127.0.0.1:15112'}},
  {command:'npm run dev -- --port 15112',cwd:root,url:'http://127.0.0.1:15112',timeout:120_000,
   env:{...process.env,VITE_DEV_FIXTURE:'false',VITE_API_BASE_URL:'http://127.0.0.1:18112',VITE_D1_API_BASE_URL:'http://127.0.0.1:18112'}},
 ],
});
