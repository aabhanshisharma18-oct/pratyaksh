"""UniversalFakeDetect image adapter pinned to the official implementation."""
from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path
from threading import Lock


ROOT = Path(__file__).parent
SOURCE_DIR = ROOT / "third_party" / "UniversalFakeDetect"
MODEL_DIR = ROOT / "models" / "universal-fake-detect"
MODEL_ID = "WisconsinAIVision/UniversalFakeDetect CLIP:ViT-L/14"
REVISION = "030495aea3300a8b54c0ec37ec7fe1dd7e63c619"
HEAD_WEIGHTS_SHA256 = "477100745713bcc957beb2b40859536859b6483fd6301b3b9293151b194c7847"
CLIP_WEIGHTS_SHA256 = "b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836"
LIMITATIONS = [
    "Candidate whole-image AI-generation detector; it is not a face-swap specialist or an authentication method.",
    "Not evaluated on the Pratyaksh held-out dataset; the score is not a calibrated probability of authenticity.",
    "The method can miss unseen generators and can flag genuine images after resizing, compression or editing.",
    "The complete image is center-cropped to 224 x 224 using the official evaluation preprocessing; no region is localized.",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_model() -> dict:
    manifest_path = SOURCE_DIR / ".pratyaksh-source.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Run python setup_day23_models.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("revision") != REVISION:
        raise ValueError("UniversalFakeDetect source revision is not pinned")
    head = SOURCE_DIR / "pretrained_weights" / "fc_weights.pth"
    clip = MODEL_DIR / "ViT-L-14.pt"
    if _sha256(head) != HEAD_WEIGHTS_SHA256:
        raise ValueError("UniversalFakeDetect classifier checksum mismatch")
    if not clip.is_file():
        raise FileNotFoundError("CLIP ViT-L/14 checkpoint is not downloaded")
    if _sha256(clip) != CLIP_WEIGHTS_SHA256:
        raise ValueError("CLIP ViT-L/14 checksum mismatch")
    return {
        "model_id": MODEL_ID,
        "revision": REVISION,
        "head_sha256": HEAD_WEIGHTS_SHA256,
        "backbone_sha256": CLIP_WEIGHTS_SHA256,
    }


def model_files_present() -> bool:
    return (
        (SOURCE_DIR / ".pratyaksh-source.json").is_file()
        and (SOURCE_DIR / "pretrained_weights" / "fc_weights.pth").is_file()
        and (MODEL_DIR / "ViT-L-14.pt").is_file()
    )


class ImageDetector:
    def __init__(self):
        self.lock = Lock()
        self.backbone = None
        self.head = None
        self.device = None
        self.manifest = None

    def _load(self) -> None:
        import torch

        self.manifest = verify_model()
        if str(SOURCE_DIR) not in sys.path:
            sys.path.insert(0, str(SOURCE_DIR))
        if "pkg_resources" not in sys.modules:
            import packaging
            import packaging.version
            compatibility = types.ModuleType("pkg_resources")
            compatibility.packaging = packaging
            sys.modules["pkg_resources"] = compatibility
        from models.clip import clip

        backbone, _ = clip.load(
            str(MODEL_DIR / "ViT-L-14.pt"), device="cpu", jit=False
        )
        head = torch.nn.Linear(768, 1)
        state = torch.load(
            SOURCE_DIR / "pretrained_weights" / "fc_weights.pth",
            map_location="cpu",
            weights_only=True,
        )
        if set(state) != {"weight", "bias"} or tuple(state["weight"].shape) != (1, 768):
            raise ValueError("Unexpected UniversalFakeDetect classifier structure")
        head.load_state_dict(state, strict=True)
        self.backbone = backbone.float().eval()
        self.head = head.float().eval()
        self.device = "cpu"

    @staticmethod
    def _official_eval_preprocess(image):
        from torchvision.transforms import CenterCrop, Compose, Normalize, ToTensor

        return Compose(
            [
                CenterCrop(224),
                ToTensor(),
                Normalize(
                    (0.48145466, 0.4578275, 0.40821073),
                    (0.26862954, 0.26130258, 0.27577711),
                ),
            ]
        )(image)

    def predict(self, image):
        with self.lock:
            import torch

            if self.backbone is None:
                self._load()
            tensor = self._official_eval_preprocess(image).unsqueeze(0).to("cpu")
            with torch.inference_mode():
                features = self.backbone.encode_image(tensor).float()
                logit = self.head(features).flatten()[0]
                synthetic_score = torch.sigmoid(logit).item()
            return {
                "deepfake_score": synthetic_score,
                "class_scores": {
                    "Realism": 1.0 - synthetic_score,
                    "Deepfake": synthetic_score,
                },
                "raw_logit": float(logit.item()),
                "device": self.device,
                "weights_sha256": self.manifest["head_sha256"],
                "backbone_sha256": self.manifest["backbone_sha256"],
            }
