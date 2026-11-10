import hashlib
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.evaluate_predictions import (
    score_predictions,
    select_threshold,
    validate_manifest,
)
from evaluation.run_image_manifest import run_samples


def sample(sample_id, label, split, group_id):
    return {
        "sample_id": sample_id,
        "path": sample_id + ".png",
        "sha256": "0" * 64,
        "label": label,
        "split": split,
        "group_id": group_id,
        "source": "unit test",
        "terms": "unit test",
        "media_type": "image",
        "manipulation_type": "none" if label == "genuine" else "face_swap",
        "ground_truth": {"basis": "unit-test fixture"},
        "transformation": "none",
    }


class EvaluationTests(unittest.TestCase):
    def test_manifest_runner_hashes_and_scores_local_image(self):
        class Detector:
            def predict(self, image):
                self.size = image.size
                return {"deepfake_score": 0.25}

        with TemporaryDirectory() as folder:
            path = Path(folder) / "sample.png"
            Image.new("RGB", (64, 48), "white").save(path)
            item = sample("a", "genuine", "development", "g-a")
            item["path"] = path.name
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            detector = Detector()
            records = run_samples([item], Path(folder), "development", detector)
        self.assertEqual(records[0]["execution_status"], "completed")
        self.assertEqual(records[0]["deepfake_score"], 0.25)
        self.assertEqual(records[0]["width"], 64)
        self.assertEqual(detector.size, (64, 48))

    def test_manifest_runner_accepts_face_candidate_score(self):
        class Detector:
            def predict(self, image):
                return {
                    "execution_status": "completed",
                    "face_forgery_score": 0.75,
                }

        with TemporaryDirectory() as folder:
            path = Path(folder) / "sample.png"
            Image.new("RGB", (64, 48), "white").save(path)
            item = sample("face", "synthetic", "development", "g-face")
            item["path"] = path.name
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            records = run_samples(
                [item],
                Path(folder),
                "development",
                Detector(),
                score_key="face_forgery_score",
                model_id="face-test",
                model_revision="test-revision",
                preprocessing_version="test-preprocessing",
            )

        self.assertEqual(records[0]["execution_status"], "completed")
        self.assertEqual(records[0]["deepfake_score"], 0.75)
        self.assertEqual(records[0]["model_id"], "face-test")

    def test_manifest_runner_reports_no_face_as_unavailable(self):
        class Detector:
            def predict(self, image):
                return {
                    "execution_status": "no_face",
                    "face_forgery_score": None,
                }

        with TemporaryDirectory() as folder:
            path = Path(folder) / "sample.png"
            Image.new("RGB", (64, 48), "white").save(path)
            item = sample("no-face", "genuine", "development", "g-no-face")
            item["path"] = path.name
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            records = run_samples(
                [item],
                Path(folder),
                "development",
                Detector(),
                score_key="face_forgery_score",
            )

        self.assertEqual(records[0]["execution_status"], "failed")
        self.assertIn("no face was detected", records[0]["error"])

    def test_metrics_and_unavailable_are_reported_separately(self):
        samples = [
            sample("a", "synthetic", "test", "g-a"),
            sample("b", "genuine", "test", "g-b"),
            sample("c", "synthetic", "test", "g-c"),
        ]
        predictions = [
            {"sample_id": "a", "execution_status": "completed", "deepfake_score": 0.9},
            {"sample_id": "b", "execution_status": "completed", "deepfake_score": 0.1},
            {"sample_id": "c", "execution_status": "failed", "error": "test failure"},
        ]
        result = score_predictions(samples, predictions, 0.5, "test")
        self.assertEqual(result["examined_count"], 2)
        self.assertEqual(result["coverage"], 0.666667)
        self.assertEqual(result["metrics"]["accuracy"], 1.0)
        self.assertEqual(result["metrics"]["false_negative_rate"], 0.0)
        self.assertEqual(result["metrics"]["false_positive_rate"], 0.0)
        self.assertEqual(result["metrics"]["roc_auc"], 1.0)
        self.assertEqual(result["metrics"]["average_precision"], 1.0)
        self.assertEqual(result["unavailable"][0]["sample_id"], "c")

    def test_false_negative_and_manipulation_breakdown_are_visible(self):
        samples = [
            sample("fake", "synthetic", "test", "g-fake"),
            sample("real", "genuine", "test", "g-real"),
        ]
        predictions = [
            {"sample_id": "fake", "execution_status": "completed", "deepfake_score": 0.1},
            {"sample_id": "real", "execution_status": "completed", "deepfake_score": 0.2},
        ]
        result = score_predictions(samples, predictions, 0.5, "test")
        self.assertEqual(result["confusion_matrix"]["fn"], 1)
        self.assertEqual(result["metrics"]["false_negative_rate"], 1.0)
        self.assertEqual(
            result["by_manipulation_type"]["face_swap"]["synthetic_recall"], 0.0
        )

    def test_group_leakage_is_rejected(self):
        manifest = {
            "schema_version": "1.0",
            "samples": [
                sample("a", "genuine", "development", "same-source"),
                sample("b", "synthetic", "test", "same-source"),
            ],
        }
        with self.assertRaisesRegex(ValueError, "group leakage"):
            validate_manifest(manifest)

    def test_v11_manifest_requires_ground_truth_and_consistent_type(self):
        item = sample("a", "synthetic", "development", "g-a")
        item["manipulation_type"] = "none"
        with self.assertRaisesRegex(ValueError, "must identify a manipulation type"):
            validate_manifest({"schema_version": "1.1", "samples": [item]})

    def test_threshold_is_selected_from_development_predictions(self):
        samples = [
            sample("a", "synthetic", "development", "g-a"),
            sample("b", "genuine", "development", "g-b"),
            sample("c", "synthetic", "development", "g-c"),
            sample("d", "genuine", "development", "g-d"),
        ]
        predictions = [
            {"sample_id": "a", "execution_status": "completed", "deepfake_score": 0.9},
            {"sample_id": "b", "execution_status": "completed", "deepfake_score": 0.1},
            {"sample_id": "c", "execution_status": "completed", "deepfake_score": 0.4},
            {"sample_id": "d", "execution_status": "completed", "deepfake_score": 0.3},
        ]
        result = select_threshold(samples, predictions)
        self.assertEqual(result["selected_on_split"], "development")
        self.assertEqual(result["threshold"], 0.4)
        self.assertEqual(result["selection_metrics"]["objective_value"], 1.0)

    def test_invalid_score_is_rejected(self):
        samples = [sample("a", "genuine", "test", "g-a")]
        with self.assertRaisesRegex(ValueError, "invalid deepfake_score"):
            score_predictions(
                samples,
                [{"sample_id": "a", "execution_status": "completed", "deepfake_score": 1.2}],
                0.5,
                "test",
            )


if __name__ == "__main__":
    unittest.main()
