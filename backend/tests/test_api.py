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
from video_probe import VideoProbeError


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
        self.assertEqual(body["video"]["selection_state"], "day45_candidate_unevaluated")
        self.assertTrue(body["video"]["implemented"])
        self.assertFalse(body["video"]["evaluated"])

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

    def test_combined_image_scan_includes_face_boxes_and_shared_ids(self):
        face = {
            "execution_status": "completed", "face_count": 1, "faces_truncated": False,
            "face_forgery_score": 0.82,
            "faces": [{"bbox_xyxy": [2, 3, 40, 45], "detection_confidence": 0.95, "face_forgery_score": 0.82}],
            "device": "test",
        }
        with TemporaryDirectory() as folder, patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.detector, "predict", return_value={"deepfake_score": 0.3}), \
             patch.object(main.face_forgery_detector, "predict", return_value=face):
            response = self.client.post("/api/d1/scan", files={"file": ("x.png", png())},
                                        data={"evidence_id": "E-1", "media_type": "image"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["completed_checks"], 3)
        self.assertEqual(body["summary"]["total_checks"], 3)
        self.assertEqual(body["face_analysis"]["faces"][0]["bbox_xyxy"], [2, 3, 40, 45])
        self.assertEqual(body["face_analysis"]["width"], 64)
        for finding in body["findings"]:
            self.assertEqual(finding["run_id"], body["run_id"])
            self.assertEqual(finding["evidence_id"], "E-1")
        self.assertEqual(body["face_analysis"]["finding_id"], body["findings"][1]["finding_id"])

    def test_combined_no_face_is_completed_without_a_score(self):
        face = {"execution_status": "no_face", "face_count": 0, "face_forgery_score": None, "faces": [], "device": "test"}
        with TemporaryDirectory() as folder, patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.detector, "predict", return_value={"deepfake_score": 0.3}), \
             patch.object(main.face_forgery_detector, "predict", return_value=face):
            response = self.client.post("/api/d1/scan", files={"file": ("x.png", png())},
                                        data={"evidence_id": "E-1", "media_type": "image"})
        body = response.json()
        self.assertEqual(body["face_analysis"]["execution_status"], "no_face")
        self.assertEqual(body["findings"][1]["execution_status"], "completed")
        self.assertIsNone(body["findings"][1]["score"])
        self.assertEqual(body["summary"]["completed_checks"], 3)

    def test_missing_sbi_does_not_discard_other_image_checks(self):
        with TemporaryDirectory() as folder, patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.detector, "predict", return_value={"deepfake_score": 0.3}), \
             patch.object(main.face_forgery_detector, "predict", side_effect=FileNotFoundError):
            response = self.client.post("/api/d1/scan", files={"file": ("x.png", png())},
                                        data={"evidence_id": "E-1", "media_type": "image"})
        body = response.json()
        self.assertEqual(body["summary"]["completed_checks"], 2)
        self.assertEqual(body["summary"]["total_checks"], 3)
        self.assertEqual(body["findings"][1]["execution_status"], "unsupported")
        self.assertNotIn("face_analysis", body)

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

    def test_video_response_reports_timestamped_samples_and_unvalidated_aggregation(self):
        sampled = {
            "metadata": {
                "container": "mov,mp4",
                "codec": "h264",
                "width": 640,
                "height": 360,
                "duration_ms": 5000,
                "average_frame_rate": "24/1",
                "nominal_frame_rate": "24/1",
                "source_frame_timestamps": 120,
            },
            "requested_count": 3,
            "frames": [
                {"timestamp_ms": 833, "image": Image.new("RGB", (64, 64))},
                {"timestamp_ms": 2500, "image": Image.new("RGB", (64, 64))},
            ],
            "rejected": [{"timestamp_ms": 4167, "reason": "frame_decode_failed"}],
        }
        predictions = [
            {"deepfake_score": 0.2, "raw_logit": -1.0},
            {"deepfake_score": 0.8, "raw_logit": 1.0},
        ]
        with TemporaryDirectory() as folder, \
             patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.video_sampler, "sample", return_value=sampled), \
             patch.object(main.detector, "predict", side_effect=predictions), \
             patch.object(main, "version", return_value="test-only"):
            response = self.client.post(
                "/api/d1/analyze-video", files={"file": ("clip.mp4", b"video")}
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["finding"]["result"], "inconclusive")
        self.assertEqual(body["sampling"]["examined_samples"], 2)
        self.assertEqual(len(body["sampling"]["rejected_samples"]), 1)
        self.assertAlmostEqual(body["aggregation"]["mean_score"], 0.5)
        self.assertAlmostEqual(body["aggregation"]["maximum_score"], 0.8)
        self.assertIsNone(body["aggregation"]["threshold"])
        self.assertEqual([item["timestamp_ms"] for item in body["samples"]], [833, 2500])

    def test_video_probe_errors_and_input_bounds_are_explicit(self):
        empty = self.client.post(
            "/api/d1/analyze-video", files={"file": ("x.mp4", b"")}
        )
        self.assertEqual(empty.status_code, 400)
        oversized = self.client.post(
            "/api/d1/analyze-video",
            files={"file": ("x.mp4", b"x" * (main.MAX_VIDEO_BYTES + 1))},
        )
        self.assertEqual(oversized.status_code, 413)
        with patch.object(
            main.video_sampler,
            "sample",
            side_effect=VideoProbeError(422, "Video container or streams could not be decoded"),
        ):
            corrupt = self.client.post(
                "/api/d1/analyze-video", files={"file": ("x.mp4", b"not-video")}
            )
        self.assertEqual(corrupt.status_code, 422)
        self.assertIn("could not be decoded", corrupt.json()["detail"])

    @unittest.skipUnless(main.video_sampler.available(), "FFmpeg tools are unavailable")
    def test_real_video_fixture_is_sampled_without_running_real_model(self):
        fixture = Path(__file__).resolve().parents[2] / "PRATYAKSH-test-evidence" / "04-motion-test.mp4"
        if not fixture.is_file():
            self.skipTest("Video fixture is unavailable")
        prediction = {"deepfake_score": 0.4, "raw_logit": -0.4}
        with TemporaryDirectory() as folder, \
             patch.object(main, "ROOT", Path(folder)), \
             patch.object(main.detector, "predict", return_value=prediction), \
             patch.object(main, "version", return_value="test-only"):
            response = self.client.post(
                "/api/d1/analyze-video",
                files={"file": (fixture.name, fixture.read_bytes(), "video/mp4")},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["video"]["duration_ms"], 5000)
        self.assertEqual(body["sampling"]["requested_samples"], 3)
        self.assertEqual(body["sampling"]["examined_samples"], 3)
        self.assertTrue(all(item["timestamp_ms"] >= 0 for item in body["samples"]))


if __name__ == "__main__":
    unittest.main()
