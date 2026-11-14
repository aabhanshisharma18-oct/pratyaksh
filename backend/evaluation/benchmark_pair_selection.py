"""Measured local pair-selection comparison on generated geometric controls, not deepfake accuracy."""
import argparse
from contextlib import nullcontext
import io
import json
from pathlib import Path
import statistics
import time
from unittest.mock import patch

import numpy as np
from PIL import Image,ImageDraw
import provenance
import provenance_pair_planner as planner


def greedy(candidates,budget):
    remaining=set(range(len(candidates)));selected=set();uncovered={n for a,b,_ in candidates for n in (a,b)}
    while uncovered:
        k=max(remaining,key=lambda i:(len(set(candidates[i][:2])&uncovered),candidates[i][2],-i))
        selected.add(k);remaining.remove(k);uncovered-=set(candidates[k][:2])
        if len(selected)>budget:raise ValueError('Greedy coverage needs a larger budget')
    for k in sorted(remaining,key=lambda i:(-candidates[i][2],i))[:budget-len(selected)]:selected.add(k)
    return selected,'GREEDY_BASELINE',None


def fixtures():
    def texture(seed):
        rng=np.random.default_rng(seed);image=Image.new('RGB',(360,270),'#ece7db');draw=ImageDraw.Draw(image)
        for _ in range(180):
            x,y=map(int,rng.integers([0,0],[350,260]));r=int(rng.integers(2,12))
            draw.ellipse((x,y,x+r,y+r),fill=tuple(map(int,rng.integers(0,210,3))))
        return image
    base=texture(123);edit=base.copy();ImageDraw.Draw(edit).rectangle((15,15,140,40),fill='navy')
    images=[('base.png',base),('copy.png',base.copy()),('crop.png',base.crop((35,20,335,245))),('text-edit.png',edit)]
    images += [(f'control-{seed}.png',texture(seed)) for seed in range(8)]
    result=[]
    for name,image in images:
        stream=io.BytesIO();image.save(stream,format='PNG');result.append((name,stream.getvalue()));image.close()
    return result


def links(report):
    return {tuple(sorted((edge['left_id'],edge['right_id']))) for edge in report['relationships']
            if edge['kind'] in {'exact_copy','matching_content'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=3);args=parser.parse_args()
    if args.output.exists():parser.error('Use a new result file')
    if not 1<=args.repeats<=10:parser.error('repeats must be between 1 and 10')
    items=fixtures();provenance.analyze_images(items) # untimed warm-up
    timings={key:[] for key in ['all_pairs','greedy_12','cp_sat_12']};reports={}
    # Rotate mode order so a single initial cache/startup cost is not assigned to one method.
    modes=list(timings)
    for repeat in range(args.repeats):
        for mode in modes[repeat%3:]+modes[:repeat%3]:
            context=patch.object(planner,'choose_pairs',greedy) if mode=='greedy_12' else nullcontext()
            start=time.perf_counter()
            with context:report=provenance.analyze_images(items,pair_budget=None if mode=='all_pairs' else 12)
            timings[mode].append((time.perf_counter()-start)*1000);reports[mode]=report
    reference=links(reports['all_pairs']);results={}
    for mode,report in reports.items():
        found=links(report);plan=report['pair_selection']
        results[mode]={'runtime_ms':timings[mode],'median_runtime_ms':statistics.median(timings[mode]),
          'eligible_visual_pairs':plan['eligible_visual_pairs'],'selected_visual_pairs':plan['selected_visual_pairs'],
          'unexamined_visual_pairs':len(plan['unexamined_pairs']),'planner_runtime_ms_last_run':plan['planning_runtime_ms'],
          'links_found':len(found),'reference_links_retained':len(reference & found),'reference_links_missed':len(reference-found),
          'link_ids':sorted(found),'solver_status':plan['solver_status']}
    candidates=[(i,j,64-(i^j).bit_count()) for i in range(100) for j in range(i+1,100)]
    start=time.perf_counter();selected,status,_=planner.choose_pairs(candidates,200)
    scale={'items':100,'eligible_pairs':len(candidates),'budget':200,'selected_pairs':len(selected),
           'covered_items':len({node for k in selected for node in candidates[k][:2]}),
           'solver_status':status,'runtime_ms':(time.perf_counter()-start)*1000,
           'scope':'Planner-only synthetic integer priorities. No images decoded or SIFT/RANSAC run; not end-to-end 100-file support.'}
    result={'fixture':'12 generated geometric controls; four related files plus eight unrelated source constructions',
      'budget':12,'repeats':args.repeats,'untimed_warmups':1,'results':results,'scale_check':scale,
      'notes':['Local pilot only, not deepfake detection accuracy or a representative provenance benchmark.',
               'Reference retention is relative to this matcher, not ground-truth recall.',
               'Timing includes per-file preparation and metadata checks, not only pair matching.',
               'All measured runs are reported; no faster-run selection. Current public upload cap stays 12.',
               'Fewer pair comparisons do not establish better matching accuracy or faster end-to-end processing.']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
