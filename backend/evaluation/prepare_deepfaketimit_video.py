"""Build a subject-separated DeepfakeTIMIT video pilot.

The script uses already-downloaded official archives. Genuine VidTIMIT JPEG
sequences and manipulated DeepfakeTIMIT AVIs are both normalized to silent H.264
MP4 at 25 fps before evaluation, avoiding a trivial container/audio distinction.
Derived media and the local manifest are ignored by Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

from evaluation.evaluate_predictions import validate_manifest
from evaluation.prepare_deepfaketimit import (
    DEEPFAKE_ARCHIVE_MD5,
    DEEPFAKE_DOI,
    DEFAULT_DATASET_ROOT,
    VIDTIMIT_SOURCE,
    md5_file,
    subject_configuration,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEDIA_ROOT = ROOT / "evaluation" / "media" / "deepfaketimit-video"
DEFAULT_MANIFEST = ROOT / "evaluation" / "manifest.deepfaketimit-video.local.json"
FRAME_RATE = 25
WIDTH = 512
HEIGHT = 384


def _run_ffmpeg(command: list[str]) -> None:
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=120,
    )
    if process.returncode:
        message = process.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"FFmpeg normalization failed: {message[-500:]}")


def _normalized_command(input_args: list[str], output: Path) -> list[str]:
    return [
        "ffmpeg", "-v", "error", "-y", *input_args,
        "-map", "0:v:0", "-vf", f"fps={FRAME_RATE},scale={WIDTH}:{HEIGHT}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(output),
    ]


def _speech_sequences(archive: zipfile.ZipFile, subject: str) -> dict[str, list[str]]:
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
    return {
        utterance: sorted(names, key=lambda item: int(item.rsplit("/", 1)[1]))
        for utterance, names in sorted(grouped.items())
    }


def _write_genuine_videos(zip_path: Path, subject: str, destination: Path):
    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"CRC failure in {zip_path.name}: {bad_member}")
        for utterance, members in _speech_sequences(archive, subject).items():
            output = destination / f"real-{subject}-{utterance}.mp4"
            with tempfile.TemporaryDirectory(prefix="vidtimit-frames-") as folder:
                frames = Path(folder)
                for index, member in enumerate(members, start=1):
                    (frames / f"{index:06d}.jpg").write_bytes(archive.read(member))
                _run_ffmpeg(
                    _normalized_command(
                        ["-framerate", str(FRAME_RATE), "-i", str(frames / "%06d.jpg")],
                        output,
                    )
                )
            yield utterance, output


def _write_manipulated_video(
    archive: tarfile.TarFile, member: tarfile.TarInfo, output: Path
) -> None:
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"cannot read {member.name}")
    with tempfile.TemporaryDirectory(prefix="deepfaketimit-video-") as folder:
        source = Path(folder) / "source.avi"
        source.write_bytes(stream.read())
        _run_ffmpeg(_normalized_command(["-i", str(source)], output))


def manifest_item(
    *, sample_id: str, path: Path, label: str, split: str,
    pair_id: str, subject: str,
) -> dict:
    synthetic = label == "synthetic"
    raw = path.read_bytes()
    return {
        "sample_id": sample_id,
        "path": (Path("media") / "deepfaketimit-video" / path.name).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "label": label,
        "split": split,
        "group_id": pair_id,
        "media_type": "video",
        "manipulation_type": "face_swap" if synthetic else "none",
        "ground_truth": {
            "basis": (
                "Official DeepfakeTIMIT higher-quality face-swap video"
                if synthetic else "Original VidTIMIT camera-recorded JPEG sequence"
            ),
            "reference": DEEPFAKE_DOI if synthetic else VIDTIMIT_SOURCE,
        },
        "source": f"DeepfakeTIMIT/VidTIMIT subject {subject}",
        "terms": "Academic pilot; retain dataset notices and cite both source papers",
        "transformation": (
            f"Normalized to silent H.264 MP4, {FRAME_RATE} fps, {WIDTH}x{HEIGHT}, "
            "libx264 CRF 18"
        ),
    }


def build_manifest(dataset_root: Path, media_root: Path, manifest_path: Path) -> dict:
    fake_archive = dataset_root / "deepfaketimit" / "DeepfakeTIMIT.tar.gz"
    if not fake_archive.is_file() or md5_file(fake_archive) != DEEPFAKE_ARCHIVE_MD5:
        raise ValueError("official DeepfakeTIMIT archive is missing or failed MD5 verification")
    configuration = subject_configuration()
    media_root.mkdir(parents=True, exist_ok=True)
    samples = []

    for subject, config in sorted(configuration.items()):
        subject_zip = dataset_root / "vidtimit" / f"{subject}.zip"
        if not subject_zip.is_file():
            raise FileNotFoundError(f"missing official VidTIMIT archive: {subject_zip}")
        for utterance, output in _write_genuine_videos(subject_zip, subject, media_root):
            samples.append(
                manifest_item(
                    sample_id=f"DFTV-{config['split'].upper()}-REAL-{subject}-{utterance}",
                    path=output, label="genuine", split=config["split"],
                    pair_id=config["pair_id"], subject=subject,
                )
            )

    with tarfile.open(fake_archive, "r:*") as archive:
        members = [
            member for member in archive.getmembers()
            if member.isfile()
            and member.name.startswith("DeepfakeTIMIT/higher_quality/")
            and member.name.endswith(".avi")
            and member.name.split("/")[2] in configuration
        ]
        expected = len(configuration) * 10
        if len(members) != expected:
            raise ValueError(f"expected {expected} fake videos, found {len(members)}")
        for member in sorted(members, key=lambda item: item.name):
            subject = member.name.split("/")[2]
            config = configuration[subject]
            utterance = Path(member.name).stem.split("-video-", 1)[0]
            output = media_root / f"fake-{subject}-{utterance}.mp4"
            _write_manipulated_video(archive, member, output)
            samples.append(
                manifest_item(
                    sample_id=f"DFTV-{config['split'].upper()}-FAKE-{subject}-{utterance}",
                    path=output, label="synthetic", split=config["split"],
                    pair_id=config["pair_id"], subject=subject,
                )
            )

    manifest = {
        "schema_version": "1.1",
        "name": "DeepfakeTIMIT normalized subject-separated video pilot",
        "created_at": "2026-11-11T00:00:00Z",
        "normalization": {
            "frame_rate": FRAME_RATE,
            "width": WIDTH,
            "height": HEIGHT,
            "video_codec": "H.264 libx264 CRF 18",
            "audio": "removed from both classes",
        },
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
