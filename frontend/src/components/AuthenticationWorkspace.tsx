import {translate,useI18n,type Language} from '../i18n';
import {useEffect,useMemo,useState} from 'react';

type Props={baseUrl:string;light:boolean};
type HeightMessage={type:'pratyaksh:d2-height';height:number};

export function authenticationWorkspaceUrl(baseUrl:string,light:boolean,language:Language='en'):string{
  const root=baseUrl.replace(/\/$/,'');
  return `${root}/d2?embedded=1&theme=${light?'light':'dark'}${language==='en'?'':`&lang=${language}`}`;
}

export function AuthenticationWorkspace({baseUrl,light}:Props){
  const {language}=useI18n();
  const source=useMemo(()=>authenticationWorkspaceUrl(baseUrl,light,language),[baseUrl,light,language]);
  const [height,setHeight]=useState(980);

  useEffect(()=>{
    const expectedOrigin=new URL(source,window.location.href).origin;
    const receive=(event:MessageEvent<HeightMessage>)=>{
      if(event.origin!==expectedOrigin||event.data?.type!=='pratyaksh:d2-height')return;
      const next=Number(event.data.height);
      if(Number.isFinite(next))setHeight(Math.max(680,Math.min(2600,Math.ceil(next))));
    };
    window.addEventListener('message',receive);
    return()=>window.removeEventListener('message',receive);
  },[source]);

  return <section className="authentication-workspace panel" aria-label={translate("Evidence authentication and tampering workspace")}>
    <div className="feature-help"><strong>{translate("Inspect file changes and editing clues")}</strong><p>{translate("Upload a file in this workspace, verify its stored fingerprint, then choose an examination. A matching fingerprint means the bytes have not changed since intake; it does not prove the content is genuine.")}</p></div>
    <iframe
      className="authentication-workspace-frame"
      src={source}
      title={translate("Evidence authentication and tampering workspace")}
      style={{height}}
    />
  </section>;
}
