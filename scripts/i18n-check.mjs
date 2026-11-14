import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const root=process.cwd();
const sourceRoot=path.join(root,'frontend','src');
const enPath=path.join(sourceRoot,'i18n','locales','en.ts');
const visibleAttributes=new Set(['alt','aria-label','placeholder','title']);
const allowedText=[
  /^(?:PRATYAKSH|SHA-256|UTC|SUTRAM 2026|PS02|FIXTURE|DA|AASIST)$/,
  /^(?:[A-Z]+-)?\d[\d.:/%+\-–— ]*$/,
  /^[·/|()[\]{}.,:;!?+%—–-]+$/,
];

function files(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?files(path.join(dir,entry.name)):[path.join(dir,entry.name)]);}
function source(file){return ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,file.endsWith('x')?ts.ScriptKind.TSX:ts.ScriptKind.TS);}
function propertyName(node){return ts.isIdentifier(node)||ts.isStringLiteral(node)?node.text:null;}
function unwrap(node){while(ts.isAsExpression(node)||ts.isSatisfiesExpression(node)||ts.isParenthesizedExpression(node))node=node.expression;return node;}
function collectObjectKeys(file,variable){
  const tree=source(file),keys=[];
  function flatten(object,prefix=''){for(const property of object.properties){if(!ts.isPropertyAssignment(property))continue;const name=propertyName(property.name);if(!name)continue;const key=prefix?`${prefix}.${name}`:name;if(ts.isStringLiteralLike(property.initializer))keys.push(key);else if(ts.isObjectLiteralExpression(property.initializer))flatten(property.initializer,key);}}
  tree.forEachChild(node=>{if(ts.isVariableStatement(node))for(const declaration of node.declarationList.declarations)if(ts.isIdentifier(declaration.name)&&declaration.name.text===variable&&declaration.initializer){const initializer=unwrap(declaration.initializer);if(ts.isObjectLiteralExpression(initializer))flatten(initializer)}});
  return new Set(keys);
}

const catalog=collectObjectKeys(enPath,'en'),legacyCatalog=new Set([...collectObjectKeys(path.join(sourceRoot,'i18n','legacy.ts'),'legacyHi'),...collectObjectKeys(path.join(sourceRoot,'i18n','locales','legacy-hi-extra.ts'),'legacyExtraHi')]),used=new Set(),legacyUsed=new Set(),hardcoded=[];
const codeFiles=files(sourceRoot).filter(file=>/\.tsx?$/.test(file)&&!file.includes(`${path.sep}i18n${path.sep}locales${path.sep}`)&&!file.endsWith('.test.ts')&&!file.endsWith('.test.tsx'));
for(const file of codeFiles){
  const tree=source(file),relative=path.relative(root,file).replaceAll('\\','/');
  function visit(node){
    if(ts.isStringLiteralLike(node)&&catalog.has(node.text))used.add(node.text);
    if(ts.isCallExpression(node)&&ts.isIdentifier(node.expression)&&['t','translate'].includes(node.expression.text)&&node.arguments[0]&&ts.isStringLiteralLike(node.arguments[0])&&!node.arguments[0].text.includes('.'))legacyUsed.add(node.arguments[0].text);
    if(ts.isJsxText(node)){
      const text=node.text.replace(/\s+/g,' ').trim();
      if(/[A-Za-z\u0900-\u097F]/.test(text)&&!allowedText.some(pattern=>pattern.test(text)))hardcoded.push(`${relative}:${tree.getLineAndCharacterOfPosition(node.getStart()).line+1} JSX text: ${text}`);
    }
    if(ts.isJsxAttribute(node)&&visibleAttributes.has(node.name.text)&&node.initializer&&ts.isStringLiteral(node.initializer)){
      const text=node.initializer.text.trim();
      if(/[A-Za-z\u0900-\u097F]/.test(text)&&!allowedText.some(pattern=>pattern.test(text)))hardcoded.push(`${relative}:${tree.getLineAndCharacterOfPosition(node.getStart()).line+1} ${node.name.text}: ${text}`);
    }
    ts.forEachChild(node,visit);
  }
  visit(tree);
}

const unused=[...catalog].filter(key=>!used.has(key)&&!key.endsWith('_one')&&!key.endsWith('_other'));
const intentionallyUntranslated=[/^(?:PRATYAKSH|SHA-256|UTC|SUTRAM 2026|PS02|FIXTURE|DA|AASIST|MB|MiB|X-Manifest-SHA256|SECTION 63)$/,/^python3 /,/^[·/|()[\]{}.,:;!?+%—–⌘-]+$/,/^\d/];
const untranslated=[...legacyUsed].filter(value=>!legacyCatalog.has(value)&&!intentionallyUntranslated.some(pattern=>pattern.test(value))).sort();
if(hardcoded.length)console.error(`Hardcoded user-facing literals (${hardcoded.length}):\n${hardcoded.join('\n')}`);
if(unused.length)console.error(`Unused message keys (${unused.length}):\n${unused.join('\n')}`);
if(untranslated.length)console.error(`Legacy calls without Hindi coverage (${untranslated.length}):\n${untranslated.join('\n')}`);
if(hardcoded.length||unused.length||untranslated.length)process.exit(1);
console.log(`i18n check passed: ${catalog.size} English keys, no hardcoded JSX/attributes, no unused keys.`);
