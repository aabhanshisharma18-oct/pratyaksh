import {translate} from '../../i18n';
import type {FindingCardModel} from '../../findings/viewModel';
export function ArtifactRefs({artifacts,onOpen}:{artifacts:FindingCardModel['artifacts'];onOpen:()=>void}){return <section className="finding-detail-block"><h5>{translate("Supporting artifacts")}</h5>{artifacts.length?<div className="artifact-list">{artifacts.map(item=>item.resolved?<button key={item.ref} onClick={onOpen}>{item.label}</button>:<span key={item.ref}>{item.label}</span>)}</div>:<p>{translate("No supporting artifacts referenced.")}</p>}</section>}
