import hashlib
import json
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.evaluate_predictions import (
    score_predictions,
    select_threshold,
    validate_manifest,
)
from evaluation.prepare_asvspoof2019_la import build_manifest as build_audio_manifest
from evaluation.prepare_deepfaketimit_video import manifest_item as video_manifest_item
from evaluation.reaggregate_video_predictions import reaggregate
from evaluation.run_asvspoof2019_la_archive import (
    load_journal,
    make_sample as make_archive_sample,
    protocol_rows,
    select_balanced_rows,
)
from evaluation.run_audio_manifest import run_samples as run_audio_samples
from evaluation.run_image_manifest import run_samples
from evaluation.run_video_manifest import run_samples as run_video_samples


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
    def test_video_predictions_are_reaggregated_without_rerunning_inference(self):
        records = [
            {
                "sample_id": "video-a",
                "execution_status": "completed",
                "aggregation": "mean",
                "deepfake_score": 0.4,
                "mean_frame_score": 0.4,
                "maximum_frame_score": 0.9,
                "frame_predictions": [
                    {"timestamp_ms": 100, "deepfake_score": 0.1},
                    {"timestamp_ms": 900, "deepfake_score": 0.9},
                ],
            },
            {"sample_id": "video-failed", "execution_status": "failed"},
        ]
        maximum = reaggregate(records, "maximum")
        self.assertEqual(maximum[0]["aggregation"], "maximum")
        self.assertEqual(maximum[0]["deepfake_score"], 0.9)
        self.assertEqual(maximum[0]["frame_predictions"], records[0]["frame_predictions"])
        self.assertNotIn("deepfake_score", maximum[1])
        self.assertEqual(records[0]["aggregation"], "mean")

    def test_deepfaketimit_video_item_records_normalization_and_group(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "clip.mp4"
            path.write_bytes(b"normalized-video")
            item = video_manifest_item(
                sample_id="DFTV-DEVELOPMENT-FAKE-A-SA1",
                path=path,
                label="synthetic",
                split="development",
                pair_id="PAIR-F-01",
                subject="subject-a",
            )
        self.assertEqual(item["media_type"], "video")
        self.assertEqual(item["group_id"], "PAIR-F-01")
        self.assertEqual(item["manipulation_type"], "face_swap")
        self.assertIn("H.264", item["transformation"])
        self.assertEqual(len(item["sha256"]), 64)

    def test_asvspoof_pilot_sampling_is_balanced_and_reproducible(self):
        rows = [
            {
                "speaker_id": f"S{i % 3}",
                "utterance_id": f"U{i}",
                "attack_id": "-" if i < 6 else "A01",
                "label": "bonafide" if i < 6 else "spoof",
                "line_number": i + 1,
            }
            for i in range(12)
        ]
        first = select_balanced_rows(rows, 3, "fixed-seed")
        second = select_balanced_rows(rows, 3, "fixed-seed")
        self.assertEqual(first, second)
        self.assertEqual(sum(row["label"] == "bonafide" for row in first), 3)
        self.assertEqual(sum(row["label"] == "spoof" for row in first), 3)

    def test_asvspoof_archive_protocol_and_resume_journal(self):
        with TemporaryDirectory() as folder:
            archive_path = Path(folder) / "LA.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "LA/ASVspoof2019_LA_cm_protocols/"
                    "ASVspoof2019.LA.cm.dev.trl.txt",
                    "DEV1 LA_D_1 - - bonafide\nDEV1 LA_D_2 - A01 spoof\n",
                )
                archive.writestr(
                    "LA/ASVspoof2019_LA_dev/flac/LA_D_1.flac", b"real"
                )
                archive.writestr(
                    "LA/ASVspoof2019_LA_dev/flac/LA_D_2.flac", b"fake"
                )
            with zipfile.ZipFile(archive_path) as archive:
                rows, members = protocol_rows(archive, "development")

            self.assertEqual(len(rows), 2)
            self.assertTrue(members["LA_D_2"].endswith("LA_D_2.flac"))
            sample_item = make_archive_sample(
                "development", rows[1], members["LA_D_2"], "a" * 64
            )
            self.assertEqual(sample_item["label"], "synthetic")
            self.assertEqual(
                sample_item["manipulation_type"], "asvspoof2019_la_a01"
            )

            journal = Path(folder) / "resume.jsonl"
            journal.write_text(
                json.dumps(
                    {
                        "sample": sample_item,
                        "prediction": {"execution_status": "completed"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resumed = load_journal(journal)
            self.assertIn(sample_item["sample_id"], resumed)

    def test_asvspoof_preparer_maps_official_splits_and_labels(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "LA"
            protocols = root / "ASVspoof2019_LA_cm_protocols"
            dev_audio = root / "ASVspoof2019_LA_dev" / "flac"
            test_audio = root / "ASVspoof2019_LA_eval" / "flac"
            protocols.mkdir(parents=True)
            dev_audio.mkdir(parents=True)
            test_audio.mkdir(parents=True)
            (protocols / "ASVspoof2019.LA.cm.dev.trl.txt").write_text(
                "DEV1 LA_D_1 - - bonafide\nDEV1 LA_D_2 - A01 spoof\n",
                encoding="utf-8",
            )
            (protocols / "ASVspoof2019.LA.cm.eval.trl.txt").write_text(
                "TEST1 LA_E_1 - - bonafide\nTEST1 LA_E_2 - A07 spoof\n",
                encoding="utf-8",
            )
            for directory, names in (
                (dev_audio, ("LA_D_1", "LA_D_2")),
                (test_audio, ("LA_E_1", "LA_E_2")),
            ):
                for name in names:
                    (directory / f"{name}.flac").write_bytes(name.encode())
            output = Path(folder) / "evaluation" / "manifest.audio.local.json"
            manifest = build_audio_manifest(root, output)

        self.assertEqual(len(manifest["samples"]), 4)
        by_id = {item["sample_id"]: item for item in manifest["samples"]}
        self.assertEqual(
            by_id["ASV19-LA-DEVELOPMENT-LA_D_2"]["manipulation_type"],
            "asvspoof2019_la_a01",
        )
        self.assertEqual(by_id["ASV19-LA-TEST-LA_E_1"]["label"], "genuine")

    def test_audio_manifest_runner_hashes_and_scores_local_audio(self):
        class Probe:
            def probe(self, raw):
                self.raw = raw
                return {
                    "decoded": {
                        "sample_rate_hz": 16000,
                        "decoded_duration_ms": 1250,
                    },
                    "model": {"spoof_score": 0.75},
                }

        with TemporaryDirectory() as folder:
            path = Path(folder) / "sample.wav"
            path.write_bytes(b"unit-test-audio")
            item = sample("audio", "synthetic", "development", "speaker-a")
            item.update(
                {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "media_type": "audio",
                    "manipulation_type": "text_to_speech",
                }
            )
            probe = Probe()
            records = run_audio_samples(
                [item], Path(folder), "development", probe
            )

        self.assertEqual(records[0]["execution_status"], "completed")
        self.assertEqual(records[0]["deepfake_score"], 0.75)
        self.assertEqual(records[0]["decoded_duration_ms"], 1250)
        self.assertEqual(probe.raw, b"unit-test-audio")

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

    def test_video_manifest_runner_records_frames_coverage_and_aggregation(self):
        class Sampler:
            def sample(self, raw, filename):
                self.raw = raw
                self.filename = filename
                return {
                    "metadata": {"duration_ms": 5000, "width": 640, "height": 360},
                    "requested_count": 3,
                    "frames": [
                        {"timestamp_ms": 800, "image": Image.new("RGB", (64, 48))},
                        {"timestamp_ms": 2500, "image": Image.new("RGB", (64, 48))},
                    ],
                    "rejected": [
                        {"timestamp_ms": 4200, "reason": "frame_decode_failed"}
                    ],
                }

        class Detector:
            def __init__(self):
                self.scores = iter((0.2, 0.8))

            def predict(self, image):
                return {"deepfake_score": next(self.scores)}

        with TemporaryDirectory() as folder:
            path = Path(folder) / "sample.mp4"
            path.write_bytes(b"unit-test-video")
            item = sample("video", "synthetic", "development", "source-video")
            item.update(
                {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "media_type": "video",
                    "manipulation_type": "face_swap",
                }
            )
            sampler = Sampler()
            records = run_video_samples(
                [item], Path(folder), "development", sampler, Detector(), "mean"
            )

        record = records[0]
        self.assertEqual(record["execution_status"], "completed")
        self.assertAlmostEqual(record["deepfake_score"], 0.5)
        self.assertAlmostEqual(record["maximum_frame_score"], 0.8)
        self.assertEqual(record["examined_samples"], 2)
        self.assertEqual(record["requested_samples"], 3)
        self.assertEqual(len(record["rejected_samples"]), 1)
        self.assertEqual(
            [frame["timestamp_ms"] for frame in record["frame_predictions"]],
            [800, 2500],
        )
        self.assertEqual(sampler.raw, b"unit-test-video")

    def test_video_manifest_runner_can_freeze_maximum_aggregation(self):
        class Sampler:
            def sample(self, raw, filename):
                return {
                    "metadata": {"duration_ms": 1000},
                    "requested_count": 2,
                    "frames": [
                        {"timestamp_ms": 250, "image": Image.new("RGB", (64, 64))},
                        {"timestamp_ms": 750, "image": Image.new("RGB", (64, 64))},
                    ],
                    "rejected": [],
                }

        class Detector:
            def __init__(self):
                self.values = iter((0.1, 0.9))

            def predict(self, image):
                return {"deepfake_score": next(self.values)}

        with TemporaryDirectory() as folder:
            path = Path(folder) / "sample.mp4"
            path.write_bytes(b"video")
            item = sample("maximum", "synthetic", "development", "source-max")
            item.update(
                {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "media_type": "video",
                    "manipulation_type": "face_swap",
                }
            )
            record = run_video_samples(
                [item], Path(folder), "development", Sampler(), Detector(), "maximum"
            )[0]

        self.assertAlmostEqual(record["deepfake_score"], 0.9)
        self.assertEqual(record["aggregation"], "maximum")

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
        self.assertEqual(result["metrics"]["equal_error_rate"], 0.0)
        self.assertEqual(result["confidence_intervals_95"]["accuracy"][1], 1.0)
        self.assertLess(result["confidence_intervals_95"]["accuracy"][0], 1.0)
        self.assertEqual(result["by_source_group"]["g-a"]["sample_count"], 1)
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

    def test_v11_manifest_accepts_documented_audio(self):
        item = sample("audio", "synthetic", "development", "speaker-a")
        item["media_type"] = "audio"
        item["manipulation_type"] = "voice_conversion"
        validated = validate_manifest(
            {"schema_version": "1.1", "samples": [item]}
        )
        self.assertEqual(validated[0]["media_type"], "audio")

    def test_v11_manifest_accepts_documented_video(self):
        item = sample("video", "synthetic", "development", "source-video")
        item["media_type"] = "video"
        item["path"] = "video.mp4"
        validated = validate_manifest(
            {"schema_version": "1.1", "samples": [item]}
        )
        self.assertEqual(validated[0]["media_type"], "video")

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
