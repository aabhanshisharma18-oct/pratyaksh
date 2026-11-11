"""Build an auditable manifest from a licensed ASVspoof 2019 LA checkout.

The script never downloads, copies or redistributes dataset audio. It hashes the
official development and evaluation FLAC files in place and maps the official
development/evaluation protocols to Pratyaksh development/test splits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from evaluation.evaluate_predictions import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ROOT = ROOT / "data" / "datasets" / "asvspoof2019" / "LA"
DEFAULT_MANIFEST = ROOT / "evaluation" / "manifest.asvspoof2019-la.local.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_protocol(path: Path) -> list[dict]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        columns = line.split()
        if len(columns) != 5:
            raise ValueError(f"invalid protocol row at {path.name}:{line_number}")
        speaker_id, utterance_id, _, attack_id, label = columns
        if label not in {"bonafide", "spoof"}:
            raise ValueError(f"invalid label at {path.name}:{line_number}: {label}")
        if label == "bonafide" and attack_id != "-":
            raise ValueError(f"bonafide row has an attack ID at {path.name}:{line_number}")
        if label == "spoof" and attack_id == "-":
            raise ValueError(f"spoof row lacks an attack ID at {path.name}:{line_number}")
        records.append(
            {
                "speaker_id": speaker_id,
                "utterance_id": utterance_id,
                "attack_id": attack_id,
                "label": label,
                "line_number": line_number,
            }
        )
    if not records:
        raise ValueError(f"protocol is empty: {path}")
    return records


def build_manifest(dataset_root: Path, manifest_path: Path) -> dict:
    protocols = dataset_root / "ASVspoof2019_LA_cm_protocols"
    split_config = {
        "development": (
            protocols / "ASVspoof2019.LA.cm.dev.trl.txt",
            dataset_root / "ASVspoof2019_LA_dev" / "flac",
        ),
        "test": (
            protocols / "ASVspoof2019.LA.cm.eval.trl.txt",
            dataset_root / "ASVspoof2019_LA_eval" / "flac",
        ),
    }
    samples = []
    manifest_base = manifest_path.parent.resolve()
    for split, (protocol_path, audio_dir) in split_config.items():
        if not protocol_path.is_file():
            raise FileNotFoundError(f"missing official protocol: {protocol_path}")
        for row in read_protocol(protocol_path):
            audio_path = audio_dir / f"{row['utterance_id']}.flac"
            if not audio_path.is_file():
                raise FileNotFoundError(f"missing protocol audio: {audio_path}")
            synthetic = row["label"] == "spoof"
            samples.append(
                {
                    "sample_id": f"ASV19-LA-{split.upper()}-{row['utterance_id']}",
                    "path": os.path.relpath(audio_path.resolve(), manifest_base),
                    "sha256": sha256_file(audio_path),
                    "label": "synthetic" if synthetic else "genuine",
                    "split": split,
                    "group_id": f"speaker:{row['speaker_id']}",
                    "media_type": "audio",
                    "manipulation_type": (
                        f"asvspoof2019_la_{row['attack_id'].lower()}"
                        if synthetic
                        else "none"
                    ),
                    "ground_truth": {
                        "basis": "Official ASVspoof 2019 LA protocol label",
                        "reference": f"{protocol_path.name}:{row['line_number']}",
                    },
                    "source": "ASVspoof 2019 logical-access database",
                    "terms": "ASVspoof database licence; do not redistribute audio",
                    "transformation": "none; official FLAC hashed and read in place",
                }
            )
    manifest = {
        "schema_version": "1.1",
        "name": "ASVspoof 2019 LA official development and evaluation splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples": sorted(samples, key=lambda item: item["sample_id"]),
    }
    validate_manifest(manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest = build_manifest(args.dataset_root, args.manifest)
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
