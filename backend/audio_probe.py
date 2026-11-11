"""AASIST execution probe. It deliberately produces no authenticity verdict."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Lock

import numpy as np


ROOT = Path(__file__).parent
SOURCE_DIR = ROOT / "third_party" / "aasist"
MODEL_ID = "clovaai/AASIST"
REVISION = "a04c9863f63d44471dde8a6abcb3b082b07cd1d1"
WEIGHTS_SHA256 = "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
PREPROCESSING_VERSION = "ffmpeg-mono-16khz-first64600-repeat-v1"
SAMPLE_RATE = 16_000
MODEL_SAMPLES = 64_600
MAX_DECODE_SECONDS = 30
MIN_SECONDS = 1.0
MIN_RMS = 1e-4
MODEL_CONFIG = {
    "first_conv": 128,
    "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
    "gat_dims": [64, 32],
    "pool_ratios": [0.5, 0.7, 0.5, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0],
}


class AudioProbeError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_audio_probe() -> dict:
    manifest_path = SOURCE_DIR / ".pratyaksh-source.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Run python setup_day23_models.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("revision") != REVISION:
        raise ValueError("AASIST source revision is not pinned")
    weights = SOURCE_DIR / "models" / "weights" / "AASIST.pth"
    if _sha256(weights) != WEIGHTS_SHA256:
        raise ValueError("AASIST checkpoint checksum mismatch")
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError("ffmpeg is required for audio decoding")
    return {"revision": REVISION, "weights_sha256": WEIGHTS_SHA256}


def audio_probe_files_present() -> bool:
    return (
        (SOURCE_DIR / ".pratyaksh-source.json").is_file()
        and (SOURCE_DIR / "models" / "AASIST.py").is_file()
        and (SOURCE_DIR / "models" / "weights" / "AASIST.pth").is_file()
    )


def decode_audio(raw: bytes) -> tuple[np.ndarray, dict]:
    if not raw:
        raise AudioProbeError("Empty audio file")
    with tempfile.NamedTemporaryFile(suffix=".media") as source:
        source.write(raw)
        source.flush()
        command = [
            "ffmpeg", "-nostdin", "-v", "error", "-i", source.name,
            "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-t",
            str(MAX_DECODE_SECONDS), "-f", "f32le", "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, check=False, timeout=45
            )
        except subprocess.TimeoutExpired as exc:
            raise AudioProbeError("Audio decoding timed out") from exc
    if completed.returncode != 0 or not completed.stdout:
        raise AudioProbeError("Audio cannot be decoded safely")
    samples = np.frombuffer(completed.stdout, dtype="<f4").copy()
    duration = len(samples) / SAMPLE_RATE
    if duration < MIN_SECONDS:
        raise AudioProbeError("At least 1 second of audio is required")
    if not np.isfinite(samples).all():
        raise AudioProbeError("Decoded audio contains invalid samples")
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    if not math.isfinite(rms) or rms < MIN_RMS:
        raise AudioProbeError("Audio is silent or too quiet for this probe")
    return samples, {
        "sample_rate_hz": SAMPLE_RATE,
        "channels": 1,
        "decoded_duration_ms": round(duration * 1000),
        "rms": rms,
        "decode_limit_seconds": MAX_DECODE_SECONDS,
    }


def prepare_aasist_input(samples: np.ndarray) -> np.ndarray:
    if len(samples) >= MODEL_SAMPLES:
        return samples[:MODEL_SAMPLES]
    repeats = int(MODEL_SAMPLES / len(samples)) + 1
    return np.tile(samples, repeats)[:MODEL_SAMPLES]


class AASISTProbe:
    def __init__(self):
        self.lock = Lock()
        self.model = None
        self.manifest = None

    def _load(self) -> None:
        import torch

        self.manifest = verify_audio_probe()
        module_path = SOURCE_DIR / "models" / "AASIST.py"
        spec = importlib.util.spec_from_file_location("pratyaksh_aasist", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("Cannot load pinned AASIST source")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        model = module.Model(MODEL_CONFIG)
        state = torch.load(
            SOURCE_DIR / "models" / "weights" / "AASIST.pth",
            map_location="cpu",
            weights_only=True,
        )
        model.load_state_dict(state, strict=True)
        self.model = model.to("cpu").eval()

    def predict_samples(self, samples: np.ndarray) -> dict:
        return self.predict_batch_samples([samples])[0]

    def predict_batch_samples(self, sample_batches: list[np.ndarray]) -> list[dict]:
        import torch

        if not sample_batches:
            return []
        with self.lock:
            if self.model is None:
                self._load()
            prepared = np.stack(
                [prepare_aasist_input(samples) for samples in sample_batches]
            )
            tensor = torch.from_numpy(prepared).float()
            with torch.inference_mode():
                _, logits = self.model(tensor)
                scores = torch.softmax(logits, dim=-1)
            # The official data utility maps spoof=0 and bonafide=1.
            return [
                {
                    "spoof_score": float(item_scores[0].item()),
                    "class_scores": {
                        "Spoof": float(item_scores[0].item()),
                        "Bonafide": float(item_scores[1].item()),
                    },
                    "raw_logits": [float(value) for value in item_logits.tolist()],
                    "device": "cpu",
                    "model_samples": MODEL_SAMPLES,
                    "model_duration_ms": round(MODEL_SAMPLES / SAMPLE_RATE * 1000),
                    "weights_sha256": self.manifest["weights_sha256"],
                }
                for item_scores, item_logits in zip(scores, logits)
            ]

    def probe(self, raw: bytes) -> dict:
        samples, decoded = decode_audio(raw)
        return {"decoded": decoded, "model": self.predict_samples(samples)}
