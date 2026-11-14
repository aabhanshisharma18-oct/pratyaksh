"""Face-level SBI research candidate with YuNet face extraction.

The restricted SBI source and checkpoint are never committed. This adapter uses
the official FF-c23 checkpoint, optionally with local fine-tuned weights,
and an MIT-licensed YuNet detector.
"""
from __future__ import annotations

import hashlib
import math
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
PREPROCESSING_VERSION = "yunet-0.6-letterbox32-pad12.5-resize380-rgb01-v2"
PILOT_PATH = ROOT / "evaluation/results/sbi-timit-two-blocks-20261111-232032/sbi-last-two-blocks.pt"
PILOT_SHA256 = "903f28007457c9bb6e21379a4858e87bf9ea4ca7a2ef6781ab267cac867eb97c"
PILOT_MODEL_ID = "SBI EfficientNet-B4 (Pratyaksh face-swap pilot)"
PILOT_MODEL_VERSION = "pratyaksh-two-blocks-20261111-232032"
STILL_PATH = ROOT / "evaluation/results/sbi-still-images-backbone-20261112/sbi-still-image-two-blocks.pt"
STILL_SHA256 = "08a39359e5b3a2700ff32ae27fbc908a8b7993a50caec11a4b9bd3a0f0d576c9"
STILL_MODEL_ID = "SBI EfficientNet-B4 (Pratyaksh still-image pilot)"
STILL_MODEL_VERSION = "pratyaksh-still-images-backbone-20261112"
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
    def __init__(self, *, use_pilot: bool = False, use_still_images: bool = False):
        self.use_pilot = use_pilot or use_still_images
        self.use_still_images = use_still_images
        self.lock = Lock()
        self.face_detector = None
        self.classifier = None
        self.manifest = None
        self.device = None

    @property
    def model_id(self) -> str:
        if self.use_still_images:
            return STILL_MODEL_ID
        return PILOT_MODEL_ID if self.use_pilot else MODEL_ID

    @property
    def model_version(self) -> str:
        if self.use_still_images:
            return STILL_MODEL_VERSION
        return PILOT_MODEL_VERSION if self.use_pilot else MODEL_VERSION

    def files_present(self) -> bool:
        checkpoint_path = STILL_PATH if self.use_still_images else PILOT_PATH
        return face_model_files_present() and (not self.use_pilot or checkpoint_path.is_file())

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
        if self.use_pilot:
            self._load_pilot(classifier)
        self.classifier = classifier.float().eval()
        self.device = "cpu"

    def _load_pilot(self, classifier) -> None:
        import torch
        from torch import nn

        checkpoint_path = STILL_PATH if self.use_still_images else PILOT_PATH
        checkpoint_hash = STILL_SHA256 if self.use_still_images else PILOT_SHA256
        if not checkpoint_path.is_file() or _sha256(checkpoint_path) != checkpoint_hash:
            raise FileNotFoundError("Local SBI pilot checkpoint is missing or failed verification")
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        expected_source = self.manifest
        if self.use_still_images:
            expected_source = {
                **self.manifest,
                "model_id": PILOT_MODEL_ID,
                "model_version": PILOT_MODEL_VERSION,
                "checkpoint_sha256": PILOT_SHA256,
                "base_checkpoint_sha256": SBI_SHA256,
            }
        if checkpoint["source"] != expected_source or checkpoint["preprocessing"] != PREPROCESSING_VERSION:
            raise ValueError("SBI pilot checkpoint has incompatible source or preprocessing")

        class NormalizeFeatures(nn.Module):
            def __init__(self, mean, std):
                super().__init__()
                self.register_buffer("mean", mean)
                self.register_buffer("std", std)

            def forward(self, features):
                return (features - self.mean) / self.std

        nn.Sequential(*classifier._blocks[-2:]).load_state_dict(checkpoint["last_two_blocks"])
        head = nn.Sequential(
            nn.Linear(classifier._fc.in_features, 128), nn.GELU(), nn.Dropout(0.35), nn.Linear(128, 2)
        )
        head.load_state_dict(checkpoint["head"])
        classifier._fc = nn.Sequential(NormalizeFeatures(checkpoint["mean"], checkpoint["std"]), head)
        self.manifest = {
            **self.manifest,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "checkpoint_sha256": checkpoint_hash,
            "base_checkpoint_sha256": SBI_SHA256,
        }

    @staticmethod
    def _crop_face(image, box):
        import cv2

        height, width = image.shape[:2]
        x, y, box_width, box_height = box
        if not all(math.isfinite(value) for value in box) or box_width <= 0 or box_height <= 0:
            raise ValueError("face detector returned an invalid bounding box")
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

    def crop_faces(self, pil_image):
        """Return crops and coordinates in the same order used by inference."""
        import cv2
        import numpy as np

        rgb = np.asarray(pil_image.convert("RGB"))
        original_height, original_width = rgb.shape[:2]
        scale = min(1.0, 1280 / max(original_height, original_width))
        if scale < 1.0:
            detection_rgb = cv2.resize(
                rgb,
                (max(1, round(original_width * scale)), max(1, round(original_height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            detection_rgb = rgb
        content_height, content_width = detection_rgb.shape[:2]
        detection_bgr = cv2.copyMakeBorder(
            detection_rgb[:, :, ::-1].copy(), 0, max(0, 32 - content_height),
            0, max(0, 32 - content_width), cv2.BORDER_CONSTANT, value=(0, 0, 0),
        )
        detect_height, detect_width = detection_bgr.shape[:2]
        self.face_detector.setInputSize((detect_width, detect_height))
        _, detected = self.face_detector.detect(detection_bgr)
        if detected is None or len(detected) == 0:
            return [], [], False

        if detected.ndim != 2 or detected.shape[1] < 15 or not np.isfinite(detected).all():
            raise ValueError("face detector returned invalid detections")
        if np.any(detected[:, 2:4] <= 0):
            raise ValueError("face detector returned invalid face dimensions")
        rows = sorted(detected, key=lambda row: float(row[2] * row[3]), reverse=True)
        scale_x = content_width / original_width
        scale_y = content_height / original_height
        crops = []
        metadata = []
        for row in rows[:MAX_FACES]:
            x, width = float(row[0]) / scale_x, float(row[2]) / scale_x
            y, height = float(row[1]) / scale_y, float(row[3]) / scale_y
            crop, bounds = self._crop_face(rgb, (x, y, width, height))
            crops.append(crop)
            metadata.append(
                {
                    "bbox_xyxy": bounds,
                    "detection_confidence": round(float(row[14]), 6),
                }
            )
        return crops, metadata, len(rows) > MAX_FACES

    def predict(self, pil_image) -> dict:
        with self.lock:
            import torch

            if self.classifier is None:
                self._load()
            crops, metadata, truncated = self.crop_faces(pil_image)
            if not crops:
                return {
                    "execution_status": "no_face",
                    "face_count": 0,
                    "face_forgery_score": None,
                    "faces": [],
                    "device": self.device,
                    **self.manifest,
                }
            face_tensors = [torch.from_numpy(crop.transpose(2, 0, 1).copy()) for crop in crops]
            batch = torch.stack(face_tensors).float() / 255.0
            with torch.inference_mode():
                logits = self.classifier(batch)
                if logits.shape != (len(metadata), 2) or not torch.isfinite(logits).all():
                    raise ValueError("SBI returned invalid classifier outputs")
                scores = torch.softmax(logits, dim=1)[:, 1].cpu().tolist()
            for item, score in zip(metadata, scores):
                item["face_forgery_score"] = float(score)
            maximum = max(scores)
            return {
                "execution_status": "completed",
                "face_count": len(metadata),
                "faces_truncated": truncated,
                "face_forgery_score": float(maximum),
                "aggregation": "maximum face score",
                "faces": metadata,
                "device": self.device,
                "preprocessing_version": PREPROCESSING_VERSION,
                **self.manifest,
            }
