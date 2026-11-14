import {FileWarning} from 'lucide-react';
import {useI18n} from '../../i18n';
import {unsupportedInfo,type UnsupportedReason} from '../../viewer/unsupported';
export function UnsupportedMedia({reason,alert=false}:{reason:UnsupportedReason;alert?:boolean}){const{t}=useI18n();const info=unsupportedInfo(reason);return <div className="unsupported-media" role={alert?'alert':'status'}><FileWarning size={28}/><h3>{t(info.title)}</h3><p>{t(info.message)}</p><strong>{t(info.nextStep)}</strong><small>{t('Preview availability does not change the hash record or any saved finding.')}</small></div>}
