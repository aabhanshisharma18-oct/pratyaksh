import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
export default async function teardown(){await fs.rm(path.join(here,'..','.e2e-tmp'),{recursive:true,force:true})}
