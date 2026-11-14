import csv
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.prepare_dataset_expansion import inventory, merge


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        (self.root/'a.mp4').write_bytes(b'video-a');(self.root/'b.mp4').write_bytes(b'video-b')
        self.rows=[{'dataset':'first','path':'a.mp4','label':'genuine','split':'train','group_id':'source-a',
                    'manipulation_type':'none','ground_truth':'author label','terms':'reviewed research terms','source_url':'https://example.org/dataset'},
                   {'dataset':'second','path':'b.mp4','label':'synthetic','split':'test','group_id':'source-b',
                    'manipulation_type':'face_swap','ground_truth':'author label','terms':'reviewed research terms','source_url':'https://example.org/dataset'}]

    def index(self):
        path=self.root/'index.csv'
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(self.rows[0]));writer.writeheader();writer.writerows(self.rows)
        return path

    def test_preserves_splits_labels_and_fingerprints(self):
        result=merge(self.index(),1000)
        self.assertEqual(result['samples'][1]['split'],'test')
        self.assertEqual(len(result['samples'][0]['sha256']),64)
        self.assertEqual(result['audit']['unique_files'],2)

    def test_rejects_global_group_crossing_dataset_splits(self):
        self.rows[1]['group_id']='source-a'
        with self.assertRaisesRegex(ValueError,'Source group crosses'):merge(self.index(),1000)

    def test_rejects_duplicate_bytes_across_splits(self):
        (self.root/'b.mp4').write_bytes(b'video-a')
        with self.assertRaisesRegex(ValueError,'Duplicate bytes cross'):merge(self.index(),1000)

    def test_removes_same_split_duplicates(self):
        self.rows[1].update(path='a.mp4',split='train',label='genuine')
        result=merge(self.index(),1000)
        self.assertEqual(result['audit']['duplicates_removed'],1)
        self.assertEqual(len(result['samples']),1)

    def test_requires_ground_truth_and_terms(self):
        self.rows[0]['terms']=''
        with self.assertRaisesRegex(ValueError,'Missing required'):merge(self.index(),1000)

    def test_budget_is_enforced(self):
        with self.assertRaisesRegex(ValueError,'budget'):merge(self.index(),1)

    def test_inventory_does_not_count_archive_as_training_media(self):
        (self.root/'data.zip').write_bytes(b'archive')
        result=inventory([str(self.root)])
        self.assertEqual(result['roots'][0]['media_counts'],{'video':2})
        self.assertEqual(result['roots'][0]['archive_count'],1)
        self.assertEqual(result['status'],'inventory_only')
