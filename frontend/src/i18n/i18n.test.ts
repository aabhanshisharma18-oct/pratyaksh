import {describe,expect,it,vi} from 'vitest';
import {applyLanguage,readStoredLanguage,resolveMessage} from './index';
import {EN_MESSAGES} from './locales/en';
import hi from './locales/hi';

const placeholders=(value:string)=>[...value.matchAll(/\{([A-Za-z0-9_]+)\}/g)].map(match=>match[1]).sort();

describe('i18n catalogs',()=>{
  it('keeps Hindi keys inside the English source of truth',()=>{
    expect(Object.keys(hi).filter(key=>!(key in EN_MESSAGES))).toEqual([]);
  });

  it('fully covers the must-translate namespaces',()=>{
    const required=['nav.','app.','landing.','cases.','activity.','evidenceTable.','run.','findings.','technical.'];
    const missing=Object.keys(EN_MESSAGES).filter(key=>required.some(prefix=>key.startsWith(prefix))&&!(key in hi));
    expect(missing).toEqual([]);
  });

  it('keeps placeholders identical between languages',()=>{
    for(const [key,value] of Object.entries(hi))expect(placeholders(value!)).toEqual(placeholders(EN_MESSAGES[key as keyof typeof EN_MESSAGES]));
  });

  it('falls back to English and supports interpolation and plurals',()=>{
    expect(resolveMessage('cases.active','hi',hi,{count:3})).toBe('3 सक्रिय');
    expect(resolveMessage('common.item','hi',hi,{count:1})).toBe('1 वस्तु');
    expect(resolveMessage('common.item','hi',hi,{count:2})).toBe('2 वस्तुएँ');
    expect(resolveMessage('evaluation.noMetrics','hi',{},undefined)).toBe(EN_MESSAGES['evaluation.noMetrics']);
  });

  it('warns in development and returns an unknown key unchanged',()=>{
    const warn=vi.spyOn(console,'warn').mockImplementation(()=>undefined);
    expect(resolveMessage('missing.key','en',EN_MESSAGES)).toBe('missing.key');
    if(import.meta.env.DEV)expect(warn).toHaveBeenCalledOnce();
    warn.mockRestore();
  });
});

describe('language persistence',()=>{
  it('validates stored language values',()=>{
    expect(readStoredLanguage({getItem:()=> 'hi'})).toBe('hi');
    expect(readStoredLanguage({getItem:()=> 'fr'})).toBe('en');
    expect(readStoredLanguage({getItem:()=>{throw new Error('blocked')}})).toBe('en');
  });

  it('persists the language and updates the document root',()=>{
    let stored='',lang='',dataset='';
    applyLanguage('hi',{setItem:(_,value)=>{stored=value}},{get lang(){return lang},set lang(value){lang=value},dataset:{get language(){return dataset},set language(value){dataset=value}} as DOMStringMap});
    expect({stored,lang,dataset}).toEqual({stored:'hi',lang:'hi',dataset:'hi'});
  });
});
