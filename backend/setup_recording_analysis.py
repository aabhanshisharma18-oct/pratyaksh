"""Fetch the official pinned MediaPipe recording-analysis models."""
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

MODELS = {
    "face_landmarker.task": ("face_landmarker/face_landmarker",
                             "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"),
    "pose_landmarker_lite.task": ("pose_landmarker/pose_landmarker_lite",
                                  "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a"),
}

if __name__ == "__main__":
    directory = Path(__file__).parent / "models" / "recording-analysis"
    directory.mkdir(parents=True, exist_ok=True)
    for name, (model, expected) in MODELS.items():
        target = directory / name
        if not target.is_file() or sha256(target.read_bytes()).hexdigest() != expected:
            url = f"https://storage.googleapis.com/mediapipe-models/{model}/float16/1/{name}"
            with urlopen(url, timeout=30) as response:
                payload = response.read(8 * 1024 * 1024)
            if sha256(payload).hexdigest() != expected:
                raise ValueError(f"Unexpected checksum for {name}")
            target.write_bytes(payload)
        print(f"Verified {name}")
