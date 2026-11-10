"""Build a subject-separated DeepfakeTIMIT pilot image benchmark.

The script does not download data. It expects the official DeepfakeTIMIT archive
and selected VidTIMIT subject archives under ``backend/data/datasets``. Derived
frames, the local manifest, and predictions are ignored by Git.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
import tempfile
import zipfile
from pathlib import Path

import cv2
from PIL import Image

from evaluation.evaluate_predictions import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ROOT = ROOT / "data" / "datasets"
DEFAULT_MEDIA_ROOT = ROOT / "evaluation" / "media" / "deepfaketimit"
DEFAULT_MANIFEST = ROOT / "evaluation" / "manifest.deepfaketimit.local.json"
DEEPFAKE_ARCHIVE_MD5 = "79b5dcee896ab825db43f1dfbdc8fdb5"
DEEPFAKE_DOI = "https://doi.org/10.34777/s09v-3340"
VIDTIMIT_SOURCE = "https://conradsanderson.id.au/vidtimit/"

# Every source/target pair stays entirely within one split. The pilot uses four
# female/male-balanced pairs per split: 16 identities, 160 real and 160 fake
# videos in total. This avoids identity and source-video leakage.
PAIR_SPLITS = {
    "PAIR-F-01": ("development", ("fadg0", "fram1")),
    "PAIR-F-02": ("development", ("faks0", "fedw0")),
    "PAIR-M-01": ("development", ("mccs0", "mmdm2")),
    "PAIR-M-02": ("development", ("mcem0", "mdld0")),
    "PAIR-F-03": ("test", ("fcft0", "fdrd1")),
    "PAIR-F-04": ("test", ("fcmh0", "fjre0")),
    "PAIR-M-03": ("test", ("mdab0", "mpdf0")),
    "PAIR-M-04": ("test", ("mdbb0", "mrcz0")),
}


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def subject_configuration() -> dict[str, dict]:
    configured = {}
    for pair_id, (split, subjects) in PAIR_SPLITS.items():
        for subject in subjects:
            if subject in configured:
                raise ValueError(f"subject {subject} appears in more than one pair")
            configured[subject] = {"pair_id": pair_id, "split": split}
    return configured


def genuine_frames(zip_path: Path, subject: str):
    """Yield one unchanged middle JPEG frame for each of ten speech videos."""
    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"CRC failure in {zip_path.name}: {bad_member}")
        prefix = f"{subject}/video/"
        grouped: dict[str, list[str]] = {}
        for name in archive.namelist():
            parts = name.split("/")
            if (
                name.startswith(prefix)
                and len(parts) == 4
                and parts[2] not in {"head", "head2", "head3"}
                and parts[3].isdigit()
            ):
                grouped.setdefault(parts[2], []).append(name)
        if len(grouped) != 10:
            raise ValueError(f"expected 10 speech videos for {subject}, found {len(grouped)}")
        for utterance, members in sorted(grouped.items()):
            selected = sorted(members, key=lambda item: int(item.rsplit("/", 1)[1]))[
                len(members) // 2
            ]
            raw = archive.read(selected)
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            yield utterance, raw


def fake_middle_frame(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"cannot read {member.name}")
    with tempfile.NamedTemporaryFile(suffix=".avi") as temporary:
        temporary.write(stream.read())
        temporary.flush()
        capture = cv2.VideoCapture(temporary.name)
        try:
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count <= 0:
                raise ValueError(f"video has no frames: {member.name}")
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_count // 2)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"cannot decode middle frame: {member.name}")
            encoded, buffer = cv2.imencode(".png", frame)
            if not encoded:
                raise ValueError(f"cannot encode middle frame: {member.name}")
            return buffer.tobytes()
        finally:
            capture.release()


def manifest_item(
    *,
    sample_id: str,
    relative_path: Path,
    raw: bytes,
    label: str,
    split: str,
    pair_id: str,
    subject: str,
    transformation: str,
) -> dict:
    synthetic = label == "synthetic"
    return {
        "sample_id": sample_id,
        "path": relative_path.as_posix(),
        "sha256": digest_bytes(raw),
        "label": label,
        "split": split,
        "group_id": pair_id,
        "media_type": "image",
        "manipulation_type": "face_swap" if synthetic else "none",
        "ground_truth": {
            "basis": (
                "Official DeepfakeTIMIT higher-quality face-swap video"
                if synthetic
                else "Original VidTIMIT camera-recorded sequence"
            ),
            "reference": DEEPFAKE_DOI if synthetic else VIDTIMIT_SOURCE,
        },
        "source": f"DeepfakeTIMIT/VidTIMIT subject {subject}",
        "terms": "Academic pilot; retain dataset notices and cite both source papers",
        "transformation": transformation,
    }


def build_manifest(dataset_root: Path, media_root: Path, manifest_path: Path) -> dict:
    fake_archive = dataset_root / "deepfaketimit" / "DeepfakeTIMIT.tar.gz"
    if not fake_archive.is_file() or md5_file(fake_archive) != DEEPFAKE_ARCHIVE_MD5:
        raise ValueError("official DeepfakeTIMIT archive is missing or failed MD5 verification")

    configuration = subject_configuration()
    samples = []
    media_root.mkdir(parents=True, exist_ok=True)

    for subject, config in sorted(configuration.items()):
        subject_zip = dataset_root / "vidtimit" / f"{subject}.zip"
        if not subject_zip.is_file():
            raise FileNotFoundError(f"missing official VidTIMIT archive: {subject_zip}")
        for utterance, raw in genuine_frames(subject_zip, subject):
            filename = f"real-{subject}-{utterance}.jpg"
            destination = media_root / filename
            destination.write_bytes(raw)
            samples.append(
                manifest_item(
                    sample_id=f"DFT-{config['split'].upper()}-REAL-{subject}-{utterance}",
                    relative_path=Path("media") / "deepfaketimit" / filename,
                    raw=raw,
                    label="genuine",
                    split=config["split"],
                    pair_id=config["pair_id"],
                    subject=subject,
                    transformation="middle source JPEG frame; bytes unchanged",
                )
            )

    # The official download is named ``.tar.gz`` but the published bytes are
    # an uncompressed POSIX tar archive. Auto-detect the container instead of
    # trusting the extension; the MD5 above still pins the exact artifact.
    with tarfile.open(fake_archive, "r:*") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.isfile()
            and member.name.startswith("DeepfakeTIMIT/higher_quality/")
            and member.name.endswith(".avi")
            and member.name.split("/")[2] in configuration
        ]
        if len(members) != len(configuration) * 10:
            raise ValueError(f"expected {len(configuration) * 10} fake videos, found {len(members)}")
        for member in sorted(members, key=lambda item: item.name):
            subject = member.name.split("/")[2]
            config = configuration[subject]
            utterance = Path(member.name).stem.split("-video-", 1)[0]
            raw = fake_middle_frame(archive, member)
            filename = f"fake-{subject}-{utterance}.png"
            destination = media_root / filename
            destination.write_bytes(raw)
            samples.append(
                manifest_item(
                    sample_id=f"DFT-{config['split'].upper()}-FAKE-{subject}-{utterance}",
                    relative_path=Path("media") / "deepfaketimit" / filename,
                    raw=raw,
                    label="synthetic",
                    split=config["split"],
                    pair_id=config["pair_id"],
                    subject=subject,
                    transformation="middle frame decoded from official higher-quality AVI; saved losslessly as PNG",
                )
            )

    manifest = {
        "schema_version": "1.1",
        "name": "DeepfakeTIMIT subject-separated 16-identity pilot",
        "created_at": "2026-11-10T00:00:00Z",
        "samples": sorted(samples, key=lambda item: item["sample_id"]),
    }
    validate_manifest(manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--media-root", type=Path, default=DEFAULT_MEDIA_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest = build_manifest(args.dataset_root, args.media_root, args.manifest)
    counts = {
        f"{split}_{label}": sum(
            item["split"] == split and item["label"] == label
            for item in manifest["samples"]
        )
        for split in ("development", "test")
        for label in ("genuine", "synthetic")
    }
    print(json.dumps({"manifest": str(args.manifest), "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
