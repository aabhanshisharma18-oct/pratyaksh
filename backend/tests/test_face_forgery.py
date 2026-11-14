import importlib.util
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from face_forgery_detector import FaceForgeryDetector

AVAILABLE = all(importlib.util.find_spec(name) for name in ("cv2", "numpy", "torch"))


@unittest.skipUnless(AVAILABLE, "Optional face research dependencies are not installed")
class FacePreprocessingTests(unittest.TestCase):
    def detector(self, rows, logits=None):
        import numpy as np
        import torch
        from unittest.mock import Mock
        detector = FaceForgeryDetector()
        detector.face_detector = Mock()
        detector.face_detector.detect.return_value = (None, np.asarray(rows, dtype=np.float32) if rows else None)
        detector.classifier = Mock(return_value=logits if logits is not None else torch.tensor([[0.0, 1.0]]))
        detector.manifest = {}
        detector.device = "cpu"
        return detector

    def test_extreme_aspect_ratio_has_nonzero_detection_dimensions(self):
        detector = self.detector([])
        result = detector.predict(Image.new("RGB", (100000, 32)))
        detector.face_detector.setInputSize.assert_called_once_with((1280, 32))
        self.assertEqual(result["execution_status"], "no_face")
        self.assertIsNone(result["face_forgery_score"])

    def test_rounded_resize_maps_boxes_using_each_actual_dimension(self):
        row = [128, 1, 128, 2] + [0] * 10 + [0.95]
        detector = self.detector([row])
        result = detector.predict(Image.new("RGB", (10000, 32)))
        # Actual detection image is 1280 × 4. Vertical scaling is 4/32.
        self.assertEqual(result["faces"][0]["bbox_xyxy"], [875, 6, 2126, 27])

    def test_nonfinite_scores_are_rejected(self):
        import torch
        detector = self.detector([[8, 8, 24, 24] + [0] * 10 + [0.9]], torch.tensor([[float("nan"), 0.0]]))
        with self.assertRaisesRegex(ValueError, "invalid classifier outputs"):
            detector.predict(Image.new("RGB", (64, 64)))

    def test_invalid_detection_coordinates_are_rejected(self):
        detector = self.detector([[float("nan"), 8, 24, 24] + [0] * 10 + [0.9]])
        with self.assertRaisesRegex(ValueError, "invalid detections"):
            detector.predict(Image.new("RGB", (64, 64)))


if __name__ == "__main__":
    unittest.main()
