"""Fetch and pin the official Day 2-3 image and audio candidates."""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parent
SOURCES = [
    {
        "name": "UniversalFakeDetect",
        "url": "https://github.com/WisconsinAIVision/UniversalFakeDetect.git",
        "revision": "030495aea3300a8b54c0ec37ec7fe1dd7e63c619",
        "license": "MIT",
        "weight": "pretrained_weights/fc_weights.pth",
        "weight_sha256": "477100745713bcc957beb2b40859536859b6483fd6301b3b9293151b194c7847",
    },
    {
        "name": "aasist",
        "url": "https://github.com/clovaai/aasist.git",
        "revision": "a04c9863f63d44471dde8a6abcb3b082b07cd1d1",
        "license": "MIT",
        "weight": "models/weights/AASIST.pth",
        "weight_sha256": "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def install_source(item: dict) -> None:
    destination = ROOT / "third_party" / item["name"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        run("git", "clone", item["url"], str(destination))
    if not (destination / ".git").is_dir():
        raise RuntimeError(f"Refusing non-git source directory: {destination}")
    run("git", "fetch", "--depth", "1", "origin", item["revision"], cwd=destination)
    run("git", "checkout", "--detach", item["revision"], cwd=destination)
    actual = run("git", "rev-parse", "HEAD", cwd=destination)
    if actual != item["revision"]:
        raise RuntimeError("UniversalFakeDetect revision mismatch")
    if sha256(destination / item["weight"]) != item["weight_sha256"]:
        raise RuntimeError("UniversalFakeDetect checkpoint checksum mismatch")
    manifest = {
        "source": item["url"],
        "revision": actual,
        "license": item["license"],
        "checkpoint": item["weight"],
        "checkpoint_sha256": item["weight_sha256"],
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    (destination / ".pratyaksh-source.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Verified {item['name']} at {actual}")


def download_clip() -> None:
    destination = ROOT / "models" / "universal-fake-detect"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "ViT-L-14.pt"
    expected = "b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836"
    url = f"https://openaipublic.azureedge.net/clip/models/{expected}/ViT-L-14.pt"
    if not path.is_file() or sha256(path) != expected:
        temporary = path.with_suffix(".download")
        urllib.request.urlretrieve(url, temporary)
        if sha256(temporary) != expected:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Downloaded CLIP checkpoint checksum mismatch")
        temporary.replace(path)
    print(f"Verified CLIP ViT-L/14: {path}")


if __name__ == "__main__":
    for source in SOURCES:
        install_source(source)
    download_clip()
    print("Day 2-3 image and audio candidates are ready.")
