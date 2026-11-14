import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runs.video_mapper import map_video_response


def payload(samples, rejected, requested=2):
    return {
        "finding": {
            "finding_id": "old", "run_id": "old", "evidence_id": "old",
            "category": "synthetic_media", "execution_status": "completed", "result": "inconclusive",
            "observation": "aggregate", "method": "candidate", "method_version": "v1", "scope": "samples",
            "score": {"value": 0.5, "range": [0, 1], "positive_class": "Deepfake",
                      "interpretation": "raw", "calibration_status": "uncalibrated"},
            "location": None, "support_refs": [], "limitations": ["bounded"],
            "review_status": "unreviewed", "fixture": False,
        },
        "video": {"duration_ms": 10000, "codec": "h264"},
        "sampling": {"policy": "two-second bins", "requested_samples": requested,
                     "examined_samples": len(samples), "rejected_samples": rejected},
        "samples": samples,
    }


class VideoRunMapperTests(unittest.TestCase):
    def test_maps_timestamps_scores_and_rejected_samples(self):
        result = map_video_response(payload(
            [{"sample_id": "FRAME-001", "timestamp_ms": 1000, "deepfake_score": 0.7, "raw_logit": 1.2}],
            [{"timestamp_ms": 5000, "reason": "frame_decode_failed"}],
        ), "RUN-new", "EVID-1")
        self.assertEqual(result["findings"][0]["location"]["timestamp_ms"], 1000)
        self.assertEqual(result["findings"][0]["score"]["value"], 0.7)
        self.assertEqual(result["coverage"]["percent"], 50.0)
        self.assertEqual(result["coverage"]["samples"][1]["status"], "unexamined")
        self.assertTrue(result["summary"]["partial_coverage"])

    def test_zero_and_full_coverage(self):
        zero = map_video_response(payload([], [{"timestamp_ms": 1000, "reason": "decode"}], 1), "R", "E")
        full = map_video_response(payload(
            [{"sample_id": "F", "timestamp_ms": 1000, "deepfake_score": 0.1}], [], 1
        ), "R", "E")
        self.assertEqual(zero["coverage"]["percent"], 0.0)
        self.assertEqual(full["coverage"]["percent"], 100.0)
        self.assertFalse(full["summary"]["partial_coverage"])


if __name__ == "__main__":
    unittest.main()
