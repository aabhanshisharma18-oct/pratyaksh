import {translate} from '../i18n';
import React from 'react';
import type {Finding} from '../model';

export function recordedSettings(details:unknown){
 const source=typeof details==='object'&&details!==null&&!Array.isArray(details)?details as Record<string,unknown>:{};
 return ['preprocessing_version','configuration_version','configuration','threshold','trust_policy','model','weights_sha256'].map(key=>({
  key,recorded:Object.prototype.hasOwnProperty.call(source,key),value:source[key],
 }));
}

export function FindingTechnicalDetails({finding}:{finding:Finding}){
 return <div className="finding-technical-appendix"><h5>{translate("Saved technical settings")}</h5>
  <p>{translate("Settings below come only from this saved finding’s details. Missing run-level settings are not reconstructed.")}</p>
  <dl>{recordedSettings(finding.details).map(item=><React.Fragment key={item.key}><dt>{item.key}</dt><dd>{item.recorded?<code>{JSON.stringify(item.value)}{item.value===null?' (recorded without a value)':''}</code>:'Not recorded in saved finding'}</dd></React.Fragment>)}</dl>
  <p>{translate("Saved location:")} {finding.location?<code>{JSON.stringify(finding.location)}</code>:'Not recorded'}</p>
 </div>;
}
