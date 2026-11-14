import {LANGUAGES,useI18n} from '../i18n';

export function LanguageSwitcher({variant}:{variant:'app'|'landing'}){
  const {language,setLanguage,t,ready}=useI18n();
  return <div className={`language-switcher language-switcher--${variant}`} role="group" aria-label={t('language.groupLabel')} aria-busy={!ready}>
    {LANGUAGES.map(option=><button
      key={option.code}
      type="button"
      lang={option.code}
      aria-label={t('language.switchTo',{language:option.nativeName})}
      aria-pressed={language===option.code}
      onClick={()=>setLanguage(option.code)}
    >{option.label}</button>)}
  </div>;
}
