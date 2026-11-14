import {createContext,useCallback,useContext,useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {DEFAULT_LANGUAGE,isLanguage,languageDefinition,type Language} from './languages';
import {EN_MESSAGES,type MessageKey} from './locales/en';
import {legacyAliases} from './legacyAliases';

export type MessageParams=Readonly<Record<string,string|number>>;
export type Translator=(key:MessageKey|string,params?:MessageParams)=>string;
type LocaleMessages=Partial<Record<MessageKey,string>>;
type LocaleModule={default:LocaleMessages;legacy?:Readonly<Record<string,string>>};
type I18nValue={language:Language;setLanguage:(language:Language)=>void;t:Translator;ready:boolean};

const STORAGE_KEY='pratyaksh-language';
const localeModules=import.meta.glob<LocaleModule>(['./locales/*.ts','!./locales/en.ts']);
const I18nContext=createContext<I18nValue|null>(null);
const loadedLocales=new Map<Language,LocaleMessages>([['en',EN_MESSAGES]]);
const loadedLegacyLocales=new Map<Language,Readonly<Record<string,string>>>([['en',{}]]);
let currentLanguage:Language=DEFAULT_LANGUAGE;
let currentMessages:LocaleMessages=EN_MESSAGES;
let currentLegacy:Readonly<Record<string,string>>={};

export function readStoredLanguage(storage:Pick<Storage,'getItem'>|undefined=typeof localStorage==='undefined'?undefined:localStorage):Language{
  try{const value=storage?.getItem(STORAGE_KEY);return isLanguage(value)?value:DEFAULT_LANGUAGE}catch{return DEFAULT_LANGUAGE}
}

async function loadLocale(language:Language):Promise<LocaleMessages>{
  const cached=loadedLocales.get(language);if(cached)return cached;
  const loader=localeModules[`./locales/${language}.ts`];
  if(!loader)return EN_MESSAGES;
  const module=await loader(),messages=module.default;loadedLocales.set(language,messages);loadedLegacyLocales.set(language,module.legacy??{});return messages;
}

function interpolate(message:string,params?:MessageParams):string{
  if(!params)return message;
  return message.replace(/\{([A-Za-z0-9_]+)\}/g,(match,name)=>params[name]===undefined?match:String(params[name]));
}

export function resolveMessage(key:string,language:Language,messages:LocaleMessages,params?:MessageParams,legacy:Readonly<Record<string,string>>=language===currentLanguage?currentLegacy:(loadedLegacyLocales.get(language)??{})):string{
  let resolvedKey:string=legacyAliases[key]??key;
  if(typeof params?.count==='number'){
    const category=new Intl.PluralRules(languageDefinition(language).locale).select(params.count);
    const pluralKey=`${resolvedKey}_${category}`;
    if(pluralKey in EN_MESSAGES)resolvedKey=pluralKey;
  }
  const semantic=messages[resolvedKey as MessageKey]??EN_MESSAGES[resolvedKey as MessageKey];
  if(semantic)return interpolate(semantic,params);
  const legacyMessage=legacy[key];
  if(legacyMessage)return interpolate(legacyMessage,params);
  if(import.meta.env.DEV)console.warn(`[i18n] Unknown message key: ${key}`);
  return interpolate(key,params);
}

export function translate(key:MessageKey|string,params?:MessageParams,language=currentLanguage):string{
  const messages=language===currentLanguage?currentMessages:(loadedLocales.get(language)??EN_MESSAGES),legacy=language===currentLanguage?currentLegacy:(loadedLegacyLocales.get(language)??{});
  return resolveMessage(key,language,messages,params,legacy);
}

export function applyLanguage(language:Language,storage:Pick<Storage,'setItem'>|undefined,root:Pick<HTMLElement,'lang'|'dataset'>|undefined){
  try{storage?.setItem(STORAGE_KEY,language)}catch{/* Storage can be unavailable in hardened browsers. */}
  if(root){root.lang=language;root.dataset.language=language}
}

export function LanguageProvider({children}:{children:ReactNode}){
  const requested=useRef(readStoredLanguage());
  const [language,setLanguageState]=useState<Language>(DEFAULT_LANGUAGE);
  const [messages,setMessages]=useState<LocaleMessages>(EN_MESSAGES);
  const [legacy,setLegacy]=useState<Readonly<Record<string,string>>>({});
  const [ready,setReady]=useState(requested.current===DEFAULT_LANGUAGE);

  const activate=useCallback(async(next:Language)=>{
    const nextMessages=await loadLocale(next);
    setMessages(nextMessages);setLegacy(loadedLegacyLocales.get(next)??{});setLanguageState(next);setReady(true);
  },[]);
  const setLanguage=useCallback((next:Language)=>{void activate(next)},[activate]);

  useEffect(()=>{if(requested.current!==DEFAULT_LANGUAGE)void activate(requested.current)},[activate]);
  currentLanguage=language;currentMessages=messages;currentLegacy=legacy;
  useEffect(()=>{
    applyLanguage(language,typeof localStorage==='undefined'?undefined:localStorage,typeof document==='undefined'?undefined:document.documentElement);
    if(typeof document!=='undefined')document.title=resolveMessage('meta.title',language,messages,undefined,legacy);
  },[language,messages]);

  const t=useCallback<Translator>((key,params)=>resolveMessage(key,language,messages,params,legacy),[language,messages,legacy]);
  const value=useMemo<I18nValue>(()=>({language,setLanguage,t,ready}),[language,setLanguage,t,ready]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const I18nProvider=LanguageProvider;
export function useI18n(){const value=useContext(I18nContext);if(!value)throw new Error('useI18n must be used inside LanguageProvider');return value}

export {LANGUAGES,type Language} from './languages';
export type {MessageKey} from './locales/en';
export {useFormatters,formatDate,formatNumber,formatRelativeTime} from './formatters';
