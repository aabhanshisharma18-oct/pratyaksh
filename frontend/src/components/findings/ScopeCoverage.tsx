import {translate} from '../../i18n';
import type {FindingCardModel} from '../../findings/viewModel';
export function ScopeCoverage({scope,coverage}:{scope:string;coverage:FindingCardModel['coverage']}){return <section className="finding-detail-block"><h5>{translate("Scope & coverage")}</h5><p>{scope}</p><span>{translate("Run-level coverage")}</span><strong>{coverage.summary}</strong><small>{coverage.reported&&coverage.detail}</small></section>}
