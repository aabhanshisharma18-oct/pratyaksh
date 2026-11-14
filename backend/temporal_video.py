"""Optional frozen-CLIP + LSTM face-sequence experiment. Never invent weights or verdicts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from detector import CLIP_WEIGHTS_SHA256

MODEL_DIR = Path(__file__).parent / 'models' / 'temporal-video'
PREPROCESSING = 'yunet-single-face-clip-center224-l2-opening4s-8hz-v1'
MIN_FRAMES = 16
MAX_FRAMES = 32
LIMITATIONS = [
    'Research face-sequence classifier, not a calibrated probability of a deepfake.',
    'Only the opening four seconds, up to 32 frames at 8 Hz, are considered.',
    'Requires one visible face throughout; multi-face, missing-face and discontinuous clips are not scored.',
    'Box continuity is a tracking safeguard, not biometric identity verification.',
    'Does not assess audio, lip synchronization or the remainder of the video.',
    'Dataset benchmark performance does not establish reliability on unseen generators or video calls.',
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_model(hidden_size=64):
    import torch
    class FaceSequenceHead(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = torch.nn.LSTM(768, hidden_size, batch_first=True)
            self.output = torch.nn.Linear(hidden_size, 1)

        def forward(self, features):
            _, (hidden, _) = self.lstm(features)
            return self.output(hidden[-1]).squeeze(-1)
    return FaceSequenceHead()


def validate_sequence(records):
    """Do not bridge missed detections, multi-face frames, jumps or long timestamp gaps."""
    if not MIN_FRAMES <= len(records) <= MAX_FRAMES:
        raise ValueError('At least 16 and at most 32 face frames are required')
    previous = None
    for item in records:
        if item['face_count'] != 1:
            raise ValueError('Exactly one visible face is required in every sampled frame')
        t = item['timestamp_ms']
        box = item['bbox_xyxy']
        if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError('Invalid face bounding box')
        if previous:
            if not 0 < t - previous['timestamp_ms'] <= 250:
                raise ValueError('Face sequence has a missing, duplicate or discontinuous timestamp')
            a = previous['bbox_xyxy']
            intersection = max(0, min(a[2], box[2])-max(a[0], box[0])) * max(0, min(a[3], box[3])-max(a[1], box[1]))
            union = (a[2]-a[0])*(a[3]-a[1]) + (box[2]-box[0])*(box[3]-box[1])-intersection
            if intersection / union < .2:
                raise ValueError('Face position changed abruptly; sequence tracking is uncertain')
        previous = item


class FaceSequenceExtractor:
    def __init__(self, encoder):
        self.encoder = encoder
        self.cropper = None

    def extract(self, frames):
        import cv2
        import torch
        from PIL import Image
        from face_forgery_detector import FaceForgeryDetector, YUNET_PATH, YUNET_SHA256
        if self.cropper is None:
            if not YUNET_PATH.is_file() or digest(YUNET_PATH) != YUNET_SHA256:
                raise ValueError('Verified YuNet face detector is required')
            self.cropper = FaceForgeryDetector()
            self.cropper.face_detector = cv2.FaceDetectorYN.create(str(YUNET_PATH), '', (320,320), .6, .3, 5000)
        features, records = [], []
        for frame in frames:
            crops, metadata, truncated = self.cropper.crop_faces(frame['image'])
            if len(crops) != 1 or truncated:
                raise ValueError('Sequence contains missing or multiple faces; no temporal score produced')
            records.append({'timestamp_ms': frame['timestamp_ms'], 'face_count': len(crops),
                            'bbox_xyxy': metadata[0]['bbox_xyxy']})
            with Image.fromarray(crops[0]) as face:
                features.append(self.encoder.encode(face))
        validate_sequence(records)
        tensor = torch.stack(features)
        if tensor.shape != (len(records),768) or not torch.isfinite(tensor).all():
            raise ValueError('Invalid CLIP sequence features')
        return tensor, records


class TemporalVideoDetector:
    def __init__(self, encoder, model_dir=MODEL_DIR):
        self.extractor = FaceSequenceExtractor(encoder)
        self.model_dir = Path(model_dir)
        self.model = None
        self.identity = None
        self.manifest = None

    def available(self):
        return (self.model_dir/'head.pt').is_file() and (self.model_dir/'manifest.json').is_file()

    def _load(self):
        import torch
        manifest = json.loads((self.model_dir/'manifest.json').read_text())
        checkpoint_hash = digest(self.model_dir/'head.pt')
        if (manifest.get('checkpoint_sha256') != checkpoint_hash or
            manifest.get('backbone_sha256') != CLIP_WEIGHTS_SHA256 or
            manifest.get('preprocessing') != PREPROCESSING):
            raise ValueError('Temporal checkpoint identity or preprocessing mismatch')
        threshold = manifest.get('threshold')
        if not isinstance(threshold,(int,float)) or not 0 <= threshold <= 1:
            raise ValueError('Temporal development cutoff is invalid')
        model = make_model()
        model.load_state_dict(torch.load(self.model_dir/'head.pt',map_location='cpu',weights_only=True),strict=True)
        self.model, self.manifest, self.identity = model.eval(), manifest, checkpoint_hash

    def analyze(self, raw, filename, sampler):
        result = {'status':'not_trained','score':None,'screening_label':None,
                  'message':'Temporal analysis is not trained yet. The frame-based scan still runs.',
                  'method':'Frozen CLIP ViT-L/14 face features + LSTM (64 hidden units)',
                  'limitations':LIMITATIONS, 'frames':[], 'window':None, 'threshold':None}
        if not self.available():
            return result
        sampled = None
        try:
            import torch
            if self.identity != digest(self.model_dir/'head.pt'):
                self._load()
            sampled = sampler.sample(raw, filename, temporal=True)
            # Decoder omissions must not silently become an apparently complete sequence.
            if sampled['rejected']:
                raise ValueError('Some sequence frames could not be decoded')
            features, records = self.extractor.extract(sampled['frames'])
            with torch.inference_mode():
                score = float(torch.sigmoid(self.model(features.unsqueeze(0)))[0])
            if not 0 <= score <= 1:
                raise ValueError('Temporal model returned an invalid score')
            threshold = self.manifest['threshold']
            result.update(status='completed', score=score, threshold=threshold,
                          screening_label='review_recommended' if score >= threshold else 'below_pilot_cutoff',
                          message=('Face sequence crossed the research cutoff; review this sampled window.' if score >= threshold else
                                   'Face sequence stayed below the research cutoff. This does not prove the video is genuine.'),
                          frames=records, window={'start_ms':records[0]['timestamp_ms'],'end_ms':records[-1]['timestamp_ms']},
                          checkpoint_sha256=self.identity, preprocessing=PREPROCESSING,
                          validation=self.manifest.get('test',{}))
        except Exception as exc:
            # Keep the independently successful frame scan available; disclose failure explicitly.
            result.update(status='unavailable',message=f'Temporal analysis unavailable: {type(exc).__name__}: {str(exc)[:200]}')
        finally:
            if sampled:
                for frame in sampled['frames']:
                    frame['image'].close()
        return result
