"""Face-level SBI research candidate with YuNet face extraction.

The restricted SBI source and checkpoint are never committed. This adapter uses
the official FF-c23 checkpoint locally and an MIT-licensed YuNet detector.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Lock


ROOT = Path(__file__).parent
MODEL_DIR = ROOT / "models" / "face-forgery"
YUNET_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
SBI_PATH = MODEL_DIR / "sbi_ff_c23.tar"
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
SBI_SHA256 = "2b05c2ba36ccb9e9f4f9e1aae9acd443ae2e6400ce725f56104fdb175d3c3267"
MODEL_ID = "Shiohara-Yamasaki/SBI EfficientNet-B4 FF-c23"
MODEL_VERSION = "official-FF-c23-checkpoint-2022-09-10"
PREPROCESSING_VERSION = "yunet-0.6-pad12.5-resize380-rgb01-v1"
MAX_FACES = 8
LIMITATIONS = [
    "Research-only candidate; its checkpoint licence does not permit commercial use.",
    "The SBI checkpoint was trained on FaceForensics++ c23 and can miss unseen manipulation methods.",
    "YuNet replaces the RetinaFace extractor used in the original SBI evaluation, so project evaluation is required.",
    "A low signal is not proof that a face is genuine; compression, scaling and small faces can remove forensic traces.",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def face_model_files_present() -> bool:
    return YUNET_PATH.is_file() and SBI_PATH.is_file()


def verify_face_models() -> dict:
    if not YUNET_PATH.is_file() or _sha256(YUNET_PATH) != YUNET_SHA256:
        raise FileNotFoundError("YuNet is missing or failed checksum verification")
    if not SBI_PATH.is_file() or _sha256(SBI_PATH) != SBI_SHA256:
        raise FileNotFoundError("SBI FF-c23 checkpoint is missing or failed verification")
    return {
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "checkpoint_sha256": SBI_SHA256,
        "face_detector_sha256": YUNET_SHA256,
    }


class FaceForgeryDetector:
    def __init__(self):
        self.lock = Lock()
        self.face_detector = None
        self.classifier = None
        self.manifest = None
        self.device = None

    def _load(self) -> None:
        import cv2
        import torch
        from efficientnet_pytorch import EfficientNet

        self.manifest = verify_face_models()
        self.face_detector = cv2.FaceDetectorYN.create(
            str(YUNET_PATH), "", (320, 320), 0.6, 0.3, 5000
        )
        classifier = EfficientNet.from_name("efficientnet-b4", num_classes=2)
        checkpoint = torch.load(SBI_PATH, map_location="cpu", weights_only=True)
        state = checkpoint.get("model")
        if not isinstance(state, dict):
            raise ValueError("SBI checkpoint does not contain a model state")
        classifier.load_state_dict(
            {key.removeprefix("net."): value for key, value in state.items()},
            strict=True,
        )
        self.classifier = classifier.float().eval()
        self.device = "cpu"

    @staticmethod
    def _crop_face(image, box):
        import cv2

        height, width = image.shape[:2]
        x, y, box_width, box_height = box
        pad_x = box_width * 0.125
        pad_y = box_height * 0.125
        left = max(0, int(x - pad_x))
        top = max(0, int(y - pad_y))
        right = min(width, int(x + box_width + pad_x) + 1)
        bottom = min(height, int(y + box_height + pad_y) + 1)
        if right <= left or bottom <= top:
            raise ValueError("face detector returned an invalid bounding box")
        crop = image[top:bottom, left:right]
        return cv2.resize(crop, (380, 380), interpolation=cv2.INTER_LINEAR), [
            left,
            top,
            right,
            bottom,
        ]

    def predict(self, pil_image) -> dict:
        with self.lock:
            import cv2
            import numpy as np
            import torch

            if self.classifier is None:
                self._load()
            rgb = np.asarray(pil_image.convert("RGB"))
            original_height, original_width = rgb.shape[:2]
            scale = min(1.0, 1280 / max(original_height, original_width))
            if scale < 1.0:
                detection_rgb = cv2.resize(
                    rgb,
                    (round(original_width * scale), round(original_height * scale)),
                    interpolation=cv2.INTER_AREA,
                )
            else:
                detection_rgb = rgb
            detection_bgr = detection_rgb[:, :, ::-1].copy()
            detect_height, detect_width = detection_bgr.shape[:2]
            self.face_detector.setInputSize((detect_width, detect_height))
            _, detected = self.face_detector.detect(detection_bgr)
            if detected is None or len(detected) == 0:
                return {
                    "execution_status": "no_face",
                    "face_count": 0,
                    "face_forgery_score": None,
                    "faces": [],
                    "device": self.device,
                    **self.manifest,
                }

            rows = sorted(detected, key=lambda row: float(row[2] * row[3]), reverse=True)
            face_tensors = []
            metadata = []
            for row in rows[:MAX_FACES]:
                x, y, width, height = [float(value) / scale for value in row[:4]]
                crop, bounds = self._crop_face(rgb, (x, y, width, height))
                face_tensors.append(torch.from_numpy(crop.transpose(2, 0, 1).copy()))
                metadata.append(
                    {
                        "bbox_xyxy": bounds,
                        "detection_confidence": round(float(row[14]), 6),
                    }
                )
            batch = torch.stack(face_tensors).float() / 255.0
            with torch.inference_mode():
                logits = self.classifier(batch)
                scores = torch.softmax(logits, dim=1)[:, 1].cpu().tolist()
            for item, score in zip(metadata, scores):
                item["face_forgery_score"] = float(score)
            maximum = max(scores)
            return {
                "execution_status": "completed",
                "face_count": len(metadata),
                "faces_truncated": len(rows) > MAX_FACES,
                "face_forgery_score": float(maximum),
                "aggregation": "maximum face score",
                "faces": metadata,
                "device": self.device,
                "preprocessing_version": PREPROCESSING_VERSION,
                **self.manifest,
            }
