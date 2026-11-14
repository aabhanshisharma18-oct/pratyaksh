import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from temporal_video import TemporalVideoDetector, make_model, validate_sequence, PREPROCESSING, digest
from video_probe import VideoSampler
from evaluation.train_temporal_video import validate_manifest, metrics, select_threshold
from detector import CLIP_WEIGHTS_SHA256


def records():
    return [{'timestamp_ms':i*125,'face_count':1,'bbox_xyxy':[10,10,80,80]} for i in range(16)]


class TemporalSequenceTests(unittest.TestCase):
    def test_sampler_selects_dense_unique_real_timestamps(self):
        pts=list(range(0,6000,40))
        selected=VideoSampler._sequence_timestamps(pts,6000)
        self.assertEqual(len(selected),32)
        self.assertTrue(all(t in pts and t<4000 for t in selected))
        self.assertEqual(selected,sorted(set(selected)))

    def test_sequence_rejects_missing_faces_time_gaps_and_track_jumps(self):
        validate_sequence(records())
        for change in [lambda r:r[4].update(face_count=2),lambda r:r[4].update(timestamp_ms=0),
                       lambda r:r[4].update(bbox_xyxy=[200,200,300,300])]:
            r=records();change(r)
            with self.assertRaises(ValueError):validate_sequence(r)
        with self.assertRaises(ValueError):validate_sequence(records()[:3])

    def test_missing_checkpoint_never_runs_decoder_or_returns_score(self):
        with tempfile.TemporaryDirectory() as folder:
            sampler=Mock()
            result=TemporalVideoDetector(Mock(),folder).analyze(b'video','v.mp4',sampler)
            self.assertEqual(result['status'],'not_trained')
            self.assertIsNone(result['score'])
            sampler.sample.assert_not_called()

    def test_checkpoint_is_bound_to_weights_and_preprocessing(self):
        import torch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); torch.save(make_model().state_dict(),root/'head.pt')
            (root/'manifest.json').write_text(json.dumps({'checkpoint_sha256':'wrong'}))
            result=TemporalVideoDetector(Mock(),root).analyze(b'video','v.mp4',Mock())
            self.assertEqual(result['status'],'unavailable')
            self.assertIsNone(result['score'])

    def test_sequence_order_changes_model_output(self):
        import torch
        torch.manual_seed(7); model=make_model().eval()
        x=torch.randn(1,16,768)
        with torch.inference_mode():
            self.assertNotAlmostEqual(float(model(x)),float(model(x.flip(1))),places=5)

    def test_checkpoint_inference_keeps_scope_and_closes_images(self):
        import torch
        torch.manual_seed(7)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);torch.save(make_model().state_dict(),root/'head.pt')
            (root/'manifest.json').write_text(json.dumps({'checkpoint_sha256':digest(root/'head.pt'),
                'backbone_sha256':CLIP_WEIGHTS_SHA256,'preprocessing':PREPROCESSING,'threshold':.5,'test':{'n':4,'accuracy':.5,'false_positive_rate':.5}}))
            detector=TemporalVideoDetector(Mock(),root)
            detector.extractor.extract=Mock(return_value=(torch.randn(16,768),records()))
            images=[Mock() for _ in range(16)]
            sampler=Mock();sampler.sample.return_value={'frames':[{'image':im} for im in images],'rejected':[]}
            result=detector.analyze(b'video','v.mp4',sampler)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['window'],{'start_ms':0,'end_ms':1875})
            self.assertGreaterEqual(result['score'],0)
            for im in images:im.close.assert_called_once()

    def test_manifest_rejects_source_leakage_and_duplicate_video_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            rows=[]
            for split in ['train','development','test']:
                for label in [0,1]:
                    for index in [0,1]:
                        name=f'{split}-{label}-{index}.mp4';(root/name).write_bytes(name.encode())
                        rows.append({'path':name,'label':label,'group_id':name,'split':split})
            self.assertEqual(len(validate_manifest(rows,root)),12)
            rows[4]['group_id']=rows[0]['group_id']
            with self.assertRaisesRegex(ValueError,'crosses splits'):validate_manifest(rows,root)
            rows[4]['group_id']=rows[4]['path'];(root/rows[4]['path']).write_bytes((root/rows[0]['path']).read_bytes())
            with self.assertRaisesRegex(ValueError,'Duplicate'):validate_manifest(rows,root)

    def test_metrics_show_false_alarms_and_development_threshold(self):
        threshold=select_threshold([0,0,1,1],[.1,.2,.8,.9])
        measured=metrics([0,0,1,1],[.1,.9,.8,.3],threshold)
        self.assertEqual(measured['confusion_matrix'],{'tp':1,'tn':1,'fp':1,'fn':1})
        self.assertEqual(measured['false_positive_rate'],.5)
        self.assertLess(measured['accuracy_95pct_wilson'][0],.5)


if __name__=='__main__':unittest.main()
