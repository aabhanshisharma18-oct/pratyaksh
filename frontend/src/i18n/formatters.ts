import {useMemo} from 'react';
import {languageDefinition,type Language} from './languages';
import {useI18n} from './index';

export function formatDate(value:string|number|Date,language:Language,options:Intl.DateTimeFormatOptions={dateStyle:'medium',timeStyle:'short'}):string{
  return new Intl.DateTimeFormat(languageDefinition(language).locale,options).format(new Date(value));
}

export function formatNumber(value:number,language:Language,options?:Intl.NumberFormatOptions):string{
  return new Intl.NumberFormat(languageDefinition(language).locale,options).format(value);
}

export function formatRelativeTime(value:number,unit:Intl.RelativeTimeFormatUnit,language:Language):string{
  return new Intl.RelativeTimeFormat(languageDefinition(language).locale,{numeric:'auto'}).format(value,unit);
}

export function useFormatters(){
  const {language}=useI18n();
  return useMemo(()=>({
    formatDate:(value:string|number|Date,options?:Intl.DateTimeFormatOptions)=>formatDate(value,language,options),
    formatNumber:(value:number,options?:Intl.NumberFormatOptions)=>formatNumber(value,language,options),
    formatRelativeTime:(value:number,unit:Intl.RelativeTimeFormatUnit)=>formatRelativeTime(value,unit,language),
  }),[language]);
}
