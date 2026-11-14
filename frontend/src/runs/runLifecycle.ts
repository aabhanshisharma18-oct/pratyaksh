import type {RunRecord,RunStatus} from './types';
const terminal=new Set<RunStatus>(['completed','partial','failed','unsupported','cancelled']);
const allowed:Record<RunStatus,readonly RunStatus[]>={queued:['running','cancelled','failed','unsupported'],running:['completed','partial','failed','cancelled','unsupported'],completed:[],partial:[],failed:[],unsupported:[],cancelled:[]};
export const isTerminal=(status:RunStatus)=>terminal.has(status);
export function canTransition(from:RunStatus,to:RunStatus){return allowed[from].includes(to)}
export function transitionRun(run:RunRecord,to:RunStatus,now:string):RunRecord{if(!canTransition(run.execution_status,to))throw new Error(`Illegal run transition: ${run.execution_status} -> ${to}`);return {...run,execution_status:to,started_at:to==='running'?(run.started_at??now):run.started_at,completed_at:isTerminal(to)?(run.completed_at??now):run.completed_at}}
