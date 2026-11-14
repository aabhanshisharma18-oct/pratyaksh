"""Budget expensive pair verification; selected pairs are candidates, never evidence of a match."""
from __future__ import annotations

from itertools import combinations
import time


def choose_pairs(candidates, budget):
    """Maximise cheap integer priorities subject to a pair budget and file participation."""
    if type(budget) is not int or budget < 1:
        raise ValueError('Comparison budget must be a positive integer')
    if len(candidates) <= budget:
        return set(range(len(candidates))), 'ALL_WITHIN_BUDGET', None
    try:
        from ortools.sat.python import cp_model
    except ImportError as exc:
        raise ValueError('CP-SAT requires OR-Tools. Install backend/requirements-provenance.txt.') from exc
    model=cp_model.CpModel()
    variables=[model.new_bool_var(f'pair_{i}') for i in range(len(candidates))]
    model.add(sum(variables)==budget)
    nodes=sorted({node for left,right,_ in candidates for node in (left,right)})
    for node in nodes:
        model.add(sum(variables[i] for i,(left,right,_) in enumerate(candidates) if node in (left,right))>=1)
    # A priority is a retrieval heuristic, not a manipulation score or calibrated probability.
    model.maximize(sum((int(score)*10000+len(candidates)-i)*variables[i]
                       for i,(_,_,score) in enumerate(candidates)))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=2
    solver.parameters.num_search_workers=1;solver.parameters.random_seed=20261114
    status=solver.solve(model)
    name=solver.status_name(status)
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        raise ValueError(f'CP-SAT could not select a covering set ({name}). Increase the budget or choose all pairs.')
    return {i for i,var in enumerate(variables) if solver.value(var)}, name, solver.objective_value


def plan_comparisons(records, visuals, video_frames, budget=None):
    started=time.perf_counter()
    if budget is not None and (type(budget) is not int or budget<1 or budget>4950):
        raise ValueError('Comparison budget must be between 1 and 4950 pairs')
    exact=[];unsupported=[];candidates=[]
    for i,j in combinations(range(len(records)),2):
        a,b=records[i],records[j]
        if a['sha256']==b['sha256']:
            exact.append((i,j));continue
        if a['id'] in video_frames and b['id'] in video_frames:
            # No global image hash for a video. Equal priority; bounded keyframes verify selected pairs.
            candidates.append((i,j,32));continue
        if visuals[i] is not None and visuals[j] is not None:
            distance=(visuals[i]['dhash'] ^ visuals[j]['dhash']).bit_count()
            candidates.append((i,j,64-distance));continue
        unsupported.append((i,j))
    if budget is None:
        selected=set(range(len(candidates)));status='EXHAUSTIVE';objective=None
    else:
        selected,status,objective=choose_pairs(candidates,budget)
    chosen={(i,j) for index,(i,j,_) in enumerate(candidates) if index in selected}
    skipped={(i,j) for index,(i,j,_) in enumerate(candidates) if index not in selected}
    def refs(pairs):
        return [{'left_id':records[i]['id'],'right_id':records[j]['id']} for i,j in sorted(pairs)]
    return chosen,{
        'strategy':'exhaustive' if budget is None else 'cp_sat',
        'solver_status':status,'requested_budget':budget,'solver_objective':objective,
        'planning_runtime_ms':round((time.perf_counter()-started)*1000,3),
        'total_pairs':len(records)*(len(records)-1)//2,'cheap_checked_pairs':len(records)*(len(records)-1)//2,
        'eligible_visual_pairs':len(candidates),'selected_visual_pairs':len(chosen),
        'exact_pairs':refs(exact),'selected_pairs':refs(chosen),'unexamined_pairs':refs(skipped),
        'unsupported_visual_pairs':refs(unsupported),
        'scope':'All pairs receive hash/metadata checks. Only selected eligible pairs receive geometric visual verification.',
        'limitation':'Unselected pairs are unexamined, not unrelated. dHash priorities can miss crops and edited variants. '
                     'File participation does not mean all relationships were checked. Budget counts file pairs, not frame comparisons or elapsed seconds.',
    }
