import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';

const output=process.argv[2];
const sources=JSON.parse(await fs.readFile(path.join(output,'sources.json'),'utf8'));
const browser=await chromium.launch(process.env.PRATYAKSH_CHROME_CHANNEL?{channel:process.env.PRATYAKSH_CHROME_CHANNEL}:{});
try{
  const page=await browser.newPage({viewport:{width:1200,height:900},deviceScaleFactor:1});
  for(const source of sources){
    const bytes=await fs.readFile(path.join(output,source.original));
    await page.setContent(`<style>
      *{box-sizing:border-box}body{margin:0;background:#edf0f4;color:#192a42;font:16px system-ui}
      header{height:104px;background:#122b46;color:white;padding:20px 32px}
      header b{font-size:24px}nav{margin-top:12px;word-spacing:26px}
      main{display:grid;grid-template-columns:260px 1fr;padding:24px;gap:28px}
      aside,article{background:white;border:1px solid #acbbce;padding:18px}
      li{margin:15px 0}button{padding:8px 18px;margin:4px;background:#eef4fb;border:1px solid #677c95;border-radius:4px}
      #photo{display:block;width:650px;height:470px;object-fit:fill}
      footer{margin-top:16px;border-top:1px solid #8899ae;padding:12px}
      </style><header><b>PRATYAKSH Evidence Review</b><nav>Cases Inventory Workbench Findings Reports Settings</nav></header>
      <main><aside><h2>Investigation</h2><p>Evidence review workspace</p><ul>
      ${['Overview','Evidence inventory','Inspection tools','Source information','Visual comparisons','Reviewer notes','Report preview','Audit history','Export package'].map(x=>`<li>${x}</li>`).join('')}
      </ul></aside><article><h2>Media preview</h2><div><button>Fit image</button><button>Zoom in</button><button>Rotate</button><button>Full screen</button></div>
      <img id="photo" src="data:image/png;base64,${bytes.toString('base64')}">
      <footer><button>Previous</button><button>Next item</button><button>Save review</button></footer></article></main>`);
    await page.locator('#photo').evaluate(image=>image.decode());
    const {x,y,width,height}=await page.locator('#photo').boundingBox();
    source.area=[x/1200,y/900,(x+width)/1200,(y+height)/900];
    await page.screenshot({path:path.join(output,source.screenshot)});
  }
  await fs.writeFile(path.join(output,'browser.json'),JSON.stringify({browser:browser.version(),viewport:[1200,900],sources},null,2)+'\n');
}finally{await browser.close()}
