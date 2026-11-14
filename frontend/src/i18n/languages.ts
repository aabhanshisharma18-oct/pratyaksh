export const LANGUAGES=[
  {code:'en',label:'EN',nativeName:'English',locale:'en-IN'},
  {code:'hi',label:'हिं',nativeName:'हिन्दी',locale:'hi-IN'},
] as const;

export type Language=typeof LANGUAGES[number]['code'];

export const DEFAULT_LANGUAGE:Language='en';

export function isLanguage(value:unknown):value is Language{
  return typeof value==='string'&&LANGUAGES.some(language=>language.code===value);
}

export function languageDefinition(code:Language){
  return LANGUAGES.find(language=>language.code===code)!;
}
