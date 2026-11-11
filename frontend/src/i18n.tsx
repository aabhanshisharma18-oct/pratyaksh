import React,{createContext,useContext,useMemo,useState} from 'react';

type Language='en'|'hi';
const hi:Record<string,string>={
  'Cases':'मामले','Overview':'अवलोकन','Evidence':'साक्ष्य','Reports':'रिपोर्ट','Evaluation':'मूल्यांकन',
  'Methods & limits':'विधियाँ और सीमाएँ','Audit log':'ऑडिट लॉग','Settings':'सेटिंग्स','Workspace':'कार्यक्षेत्र',
  'Investigation workspace':'जाँच कार्यक्षेत्र','Local prototype':'स्थानीय प्रोटोटाइप','Search evidence, IDs, hashes…':'साक्ष्य, आईडी, हैश खोजें…',
  'Switch theme':'थीम बदलें','Help':'सहायता','Menu':'मेनू','Close navigation':'नेविगेशन बंद करें',
  'FIXTURE DATA':'फिक्स्चर डेटा','FRONTEND PROTOTYPE':'फ्रंटएंड प्रोटोटाइप','Analysis backend not connected':'विश्लेषण बैकएंड जुड़ा नहीं है',
  'Illustrative investigation · Precomputed sample findings · No live forensic analysis':'उदाहरणात्मक जाँच · पूर्व-गणित नमूना निष्कर्ष · कोई लाइव फॉरेंसिक विश्लेषण नहीं',
  'Processing status':'प्रसंस्करण स्थिति','Last run':'अंतिम रन','No run recorded':'कोई रन दर्ज नहीं','Not examined':'जाँच नहीं हुई',
  'Completed':'पूर्ण','Running':'चल रहा है','Queued':'कतार में','Failed':'विफल','Unsupported':'असमर्थित',
  'Case list':'मामलों की सूची','New case':'नया मामला','Create your first case':'अपना पहला मामला बनाएँ','No cases yet':'अभी कोई मामला नहीं',
  'Search cases':'मामले खोजें','All statuses':'सभी स्थितियाँ','Newest first':'नवीनतम पहले','Oldest first':'सबसे पुराने पहले','Title':'शीर्षक',
  'Evidence items':'साक्ष्य वस्तुएँ','Created':'बनाया गया','Status':'स्थिति','Open case':'मामला खोलें','Provenance':'उत्पत्ति',
};

type I18nValue={language:Language;setLanguage:(language:Language)=>void;t:(value:string)=>string};
const I18nContext=createContext<I18nValue|null>(null);

export function I18nProvider({children}:{children:React.ReactNode}){
  const [language,setLanguage]=useState<Language>(()=>localStorage.getItem('pratyaksh-language')==='hi'?'hi':'en');
  const value=useMemo<I18nValue>(()=>({language,setLanguage:next=>{localStorage.setItem('pratyaksh-language',next);setLanguage(next)},t:value=>language==='hi'?(hi[value]||value):value}),[language]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n():I18nValue{
  const value=useContext(I18nContext);
  if(!value)throw new Error('useI18n must be used within I18nProvider');
  return value;
}
