"""Download and verify the optional research-only face-forgery models."""
from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

import gdown


ROOT = Path(__file__).parent
MODEL_DIR = ROOT / "models" / "face-forgery"
YUNET_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
SBI_PATH = MODEL_DIR / "sbi_ff_c23.tar"
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
SBI_SHA256 = "2b05c2ba36ccb9e9f4f9e1aae9acd443ae2e6400ce725f56104fdb175d3c3267"
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
SBI_GOOGLE_DRIVE_ID = "1X0-NYT8KPursLZZdxduRQju6E52hauV0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified(path: Path, expected: str) -> bool:
    return path.is_file() and sha256(path) == expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--accept-sbi-research-license",
        action="store_true",
        help="Confirm noncommercial research use under the official SBI licence",
    )
    args = parser.parse_args()
    if not args.accept_sbi_research_license:
        parser.error(
            "SBI is restricted to noncommercial research use. Read its licence "
            "and rerun with --accept-sbi-research-license only if you accept it."
        )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not verified(YUNET_PATH, YUNET_SHA256):
        temporary = YUNET_PATH.with_suffix(".download")
        urllib.request.urlretrieve(YUNET_URL, temporary)
        if sha256(temporary) != YUNET_SHA256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("YuNet download checksum mismatch")
        temporary.replace(YUNET_PATH)

    if not verified(SBI_PATH, SBI_SHA256):
        temporary = SBI_PATH.with_suffix(".download")
        gdown.download(id=SBI_GOOGLE_DRIVE_ID, output=str(temporary), quiet=False)
        if not temporary.is_file() or sha256(temporary) != SBI_SHA256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("SBI checkpoint download checksum mismatch")
        temporary.replace(SBI_PATH)

    print(f"Verified YuNet: {YUNET_PATH}")
    print(f"Verified SBI FF-c23 checkpoint: {SBI_PATH}")
    print("Research-only face-forgery candidates are ready.")


if __name__ == "__main__":
    main()
