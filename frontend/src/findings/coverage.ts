import type {RunCoverage} from '../runs/types';
export type CoverageView={reported:boolean;summary:string;detail:string};
export function deriveCoverage(run?:{coverage:RunCoverage}):CoverageView{const coverage=run?.coverage;if(!coverage)return{reported:false,summary:'Coverage not reported',detail:'Coverage not reported'};return{reported:true,summary:`${coverage.examined} of ${coverage.planned} sampled items examined`,detail:`${coverage.examined} examined · ${coverage.rejected} rejected · ${coverage.unexamined} unexamined`}}
