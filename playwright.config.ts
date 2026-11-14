import {defineConfig,devices} from '@playwright/test';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.dirname(fileURLToPath(import.meta.url));
const database=path.join(root,'.e2e-tmp',`pratyaksh-${process.pid}.db`);

export default defineConfig({
 testDir:'./e2e',fullyParallel:true,workers:2,retries:0,timeout:45_000,
 expect:{timeout:10_000},
 globalSetup:'./e2e/global-setup.ts',globalTeardown:'./e2e/global-teardown.ts',
 reporter:[['list'],['html',{open:'never',outputFolder:'playwright-report'}]],
 use:{baseURL:'http://127.0.0.1:15173',trace:'on-first-retry',screenshot:'only-on-failure',video:'on-first-retry'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
 webServer:[
  {command:'python -m uvicorn main:app --host 127.0.0.1 --port 18000',cwd:path.join(root,'backend'),url:'http://127.0.0.1:18000/api/health',reuseExistingServer:false,timeout:120_000,env:{...process.env,PRATYAKSH_DB_PATH:database,PRATYAKSH_ENV:'test',PRATYAKSH_E2E_STUB:'1',PRATYAKSH_CORS_ORIGINS:'http://127.0.0.1:15173'}},
  {command:'npm run dev -- --port 15173',cwd:root,url:'http://127.0.0.1:15173',reuseExistingServer:false,timeout:120_000,env:{...process.env,VITE_DEV_FIXTURE:'false',VITE_API_BASE_URL:'http://127.0.0.1:18000',VITE_D1_API_BASE_URL:'http://127.0.0.1:18000',VITE_EVALUATION_BASE_URL:'http://127.0.0.1:18000/e2e-evaluation'}},
 ],
});
