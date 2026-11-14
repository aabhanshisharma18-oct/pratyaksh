import {translate} from '../../i18n';
export function LimitationsList({limitations,warning}:{limitations:string[];warning:string|null}){return <section className="finding-detail-block"><h5>{translate("Limitations")}</h5>{warning?<p className="finding-incomplete" role="alert">{warning}</p>:<ul>{limitations.map((item,index)=><li key={index}>{item}</li>)}</ul>}</section>}
