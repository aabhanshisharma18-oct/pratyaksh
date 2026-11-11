import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from PIL import Image
import main


def png(size=(64, 64)):
    output = io.BytesIO()
    Image.new("RGB", size, "white").save(output, format="PNG")
    return output.getvalue()


class Day23ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_capabilities_do_not_claim_evaluation(self):
        body = self.client.get("/api/capabilities").json()
        self.assertEqual(body["contract_version"], "1.0")
        self.assertEqual(body["image"]["selection_state"], "day23_candidate_unevaluated")
        self.assertFalse(body["image"]["evaluated"])
        self.assertEqual(
            body["image"]["face_forgery"]["selection_state"],
            "research_candidate_unevaluated",
        )
        self.assertFalse(body["image"]["face_forgery"]["evaluated"])
        self.assertEqual(body["audio"]["selection_state"], "execution_probe_only")
        self.assertFalse(body["audio"]["evaluated"])

    def test_health_reports_case_store_readiness(self):
        body = self.client.get("/api/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["case_store_ready"])

    def test_missing_image_model_returns_unavailable(self):
        with patch.object(main.detector, "predict", side_effect=FileNotFoundError):
            response = self.client.post(
                "/api/d1/analyze-image", files={"file": ("x.png", png())}
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("finding", response.json())

    def test_invalid_image_inputs_are_rejected(self):
        cases = [
            (b"", 400),
            (b"not an image", 422),
            (png((8, 8)), 422),
            (b"x" * (main.MAX_BYTES + 1), 413),
        ]
        for data, expected in cases:
            with self.subTest(expected=expected):
                response = self.client.post(
                    "/api/d1/analyze-image", files={"file": ("x.png", data)}
                )
                self.assertEqual(response.status_code, expected)

    def test_image_response_is_traceable_and_inconclusive(self):
        raw = png()
        prediction = {
            "deepfake_score": 0.9,
            "class_scores": {"Realism": 0.1, "Deepfake": 0.9},
            "raw_logit": 2.2,
            "device": "test",
            "weights_sha256": "test-head",
            "backbone_sha256": "test-backbone",
        }
        with TemporaryDirectory() as folder, patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.detector, "predict", return_value=prediction), \
             patch.object(main, "version", return_value="test-only"):
            response = self.client.post(
                "/api/d1/analyze-image", files={"file": ("x.png", raw)}
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["finding"]["result"], "inconclusive")
            self.assertIsNone(body["threshold"])
            self.assertEqual(len(body["input"]["sha256"]), 64)
            self.assertFalse(body["input"]["original_retained"])
            self.assertEqual(len(list((Path(folder) / "data" / "runs").glob("*.json"))), 1)

    def test_invalid_image_score_is_not_saved(self):
        with patch.object(main.detector, "predict", return_value={"deepfake_score": float("nan")}):
            response = self.client.post(
                "/api/d1/analyze-image", files={"file": ("x.png", png())}
            )
        self.assertEqual(response.status_code, 500)

    def test_face_forgery_response_is_traceable_and_inconclusive(self):
        prediction = {
            "execution_status": "completed",
            "face_count": 1,
            "faces_truncated": False,
            "face_forgery_score": 0.82,
            "faces": [
                {
                    "bbox_xyxy": [1, 2, 30, 40],
                    "detection_confidence": 0.95,
                    "face_forgery_score": 0.82,
                }
            ],
            "device": "test",
        }
        with TemporaryDirectory() as folder, patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.face_forgery_detector, "predict", return_value=prediction):
            response = self.client.post(
                "/api/d1/analyze-face-forgery", files={"file": ("x.png", png())}
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["finding"]["result"], "inconclusive")
        self.assertEqual(body["finding"]["score"]["value"], 0.82)
        self.assertEqual(body["model"]["face_count"], 1)
        self.assertIsNone(body["threshold"])

    def test_face_forgery_no_face_does_not_invent_a_score(self):
        prediction = {
            "execution_status": "no_face",
            "face_count": 0,
            "face_forgery_score": None,
            "faces": [],
            "device": "test",
        }
        with TemporaryDirectory() as folder, patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.face_forgery_detector, "predict", return_value=prediction):
            response = self.client.post(
                "/api/d1/analyze-face-forgery", files={"file": ("x.png", png())}
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["finding"]["execution_status"], "no_face")
        self.assertIsNone(body["finding"]["score"])

    def test_audio_probe_is_explicitly_inconclusive(self):
        output = {
            "decoded": {
                "sample_rate_hz": 16000,
                "channels": 1,
                "decoded_duration_ms": 2000,
                "rms": 0.1,
                "decode_limit_seconds": 30,
            },
            "model": {
                "spoof_score": 0.8,
                "class_scores": {"Spoof": 0.8, "Bonafide": 0.2},
                "raw_logits": [1.0, 0.0],
                "device": "test",
                "model_samples": 64600,
                "model_duration_ms": 4038,
                "weights_sha256": "test-only",
            },
        }
        with patch.object(main.audio_probe, "probe", return_value=output):
            response = self.client.post(
                "/api/d1/probe-audio", files={"file": ("voice.wav", b"test-audio")}
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"], "inconclusive")
        self.assertEqual(body["selection_state"], "execution_probe_only")
        self.assertIsNone(body["threshold"])

    def test_audio_empty_and_oversized_inputs_are_rejected(self):
        empty = self.client.post(
            "/api/d1/probe-audio", files={"file": ("x.wav", b"")}
        )
        self.assertEqual(empty.status_code, 400)
        large = self.client.post(
            "/api/d1/probe-audio",
            files={"file": ("x.wav", b"x" * (main.MAX_AUDIO_BYTES + 1))},
        )
        self.assertEqual(large.status_code, 413)


if __name__ == "__main__":
    unittest.main()
