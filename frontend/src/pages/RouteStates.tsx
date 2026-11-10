import React from 'react';
import {ArrowLeft,FolderX,MapPinOff} from 'lucide-react';
import {useI18n} from '../i18n';

export function CaseNotFound({caseId,onCases}:{caseId:string;onCases:()=>void}){
  const {t}=useI18n();
  return <div className="empty route-state"><FolderX size={36}/><h1>Case not found</h1><p>No browser-local case matches <span className="mono">{caseId}</span>.</p><button className="button primary" onClick={onCases}><ArrowLeft size={15}/>{t('Cases')}</button></div>;
}
export function RouteNotFound({path,onCases}:{path:string;onCases:()=>void}){
  const {t}=useI18n();
  return <div className="empty route-state"><MapPinOff size={36}/><h1>Page not found</h1><p>The route <span className="mono">{path}</span> does not exist.</p><button className="button primary" onClick={onCases}><ArrowLeft size={15}/>{t('Cases')}</button></div>;
}
