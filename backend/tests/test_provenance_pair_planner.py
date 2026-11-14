import io
import sys
import unittest
from itertools import combinations
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from provenance_pair_planner import choose_pairs,plan_comparisons
from provenance import analyze_images
from PIL import Image


class PairPlannerTests(unittest.TestCase):
    def test_solver_respects_budget_covers_files_and_matches_small_bruteforce_optimum(self):
        candidates=[(i,j,(i*7+j*3)%65) for i,j in combinations(range(6),2)]
        selected,status,_=choose_pairs(candidates,4)
        self.assertIn(status,{'OPTIMAL','FEASIBLE'})
        self.assertEqual(len(selected),4)
        self.assertEqual({node for k in selected for node in candidates[k][:2]},set(range(6)))
        def objective(indices):return sum(candidates[k][2]*10000+len(candidates)-k for k in indices)
        optimum=max(objective(group) for group in combinations(range(len(candidates)),4)
                    if {node for k in group for node in candidates[k][:2]}==set(range(6)))
        self.assertEqual(objective(selected),optimum)

    def test_infeasible_budget_does_not_silently_drop_file_coverage(self):
        with self.assertRaisesRegex(ValueError,'Increase the budget'):
            choose_pairs([(i,j,1) for i,j in combinations(range(6),2)],1)

    def test_exact_copies_bypass_solver_and_unsupported_pairs_are_explicit(self):
        records=[{'id':str(i),'sha256':str(i)} for i in range(4)]
        records[1]['sha256']='0'
        chosen,plan=plan_comparisons(records,[{'dhash':0},{'dhash':1},{'dhash':2},None],{},2)
        self.assertEqual(plan['exact_pairs'],[{'left_id':'0','right_id':'1'}])
        self.assertEqual(len(plan['unsupported_visual_pairs']),3)
        self.assertEqual(plan['total_pairs'],6)

    def test_unexamined_pairs_partition_eligible_pairs(self):
        records=[{'id':str(i),'sha256':str(i)} for i in range(6)]
        chosen,plan=plan_comparisons(records,[{'dhash':i} for i in range(6)],{},4)
        self.assertEqual(plan['selected_visual_pairs'],4)
        self.assertEqual(len(plan['unexamined_pairs']),11)
        selected={(p['left_id'],p['right_id']) for p in plan['selected_pairs']}
        omitted={(p['left_id'],p['right_id']) for p in plan['unexamined_pairs']}
        self.assertFalse(selected & omitted)
        self.assertEqual(len(selected|omitted),15)

    def test_exhaustive_default_does_not_require_solver(self):
        records=[{'id':str(i),'sha256':str(i)} for i in range(3)]
        with patch('provenance_pair_planner.choose_pairs',side_effect=AssertionError):
            chosen,plan=plan_comparisons(records,[{'dhash':i} for i in range(3)],{})
        self.assertEqual(len(chosen),3)
        self.assertEqual(plan['strategy'],'exhaustive')

    def test_100_item_planner_obeys_200_pair_budget(self):
        candidates=[(i,j,64-((i^j).bit_count())) for i,j in combinations(range(100),2)]
        selected,status,_=choose_pairs(candidates,200)
        self.assertEqual(len(selected),200)
        self.assertEqual({node for k in selected for node in candidates[k][:2]},set(range(100)))

    def test_image_integration_runs_only_selected_expensive_comparisons(self):
        items=[]
        for color in ['red','green','blue','navy']:
            stream=io.BytesIO();Image.new('RGB',(64,64),color).save(stream,format='PNG')
            items.append((color+'.png',stream.getvalue()))
        with patch('provenance.compare_visual',return_value=None) as compare:
            report=analyze_images(items,pair_budget=3)
        self.assertEqual(compare.call_count,3)
        self.assertEqual(len(report['pair_selection']['unexamined_pairs']),3)
        self.assertEqual(report['relationships'],[])

    def test_invalid_budgets_are_rejected(self):
        for value in [0,-1,False,1.5,4951]:
            with self.assertRaises(ValueError):plan_comparisons([],[],{},value)


if __name__=='__main__':unittest.main()
