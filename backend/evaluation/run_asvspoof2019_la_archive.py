"""Evaluate pinned AASIST directly from the official ASVspoof 2019 LA ZIP.

The corpus is never extracted.  A JSONL journal is appended after every batch,
so an interrupted multi-hour evaluation can be resumed without rescoring audio.
Final manifest and prediction JSON files are produced only when the requested
split is complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from audio_probe import (
    AASISTProbe,
    MODEL_ID,
    PREPROCESSING_VERSION,
    REVISION,
    decode_audio,
)
from evaluation.evaluate_predictions import validate_manifest
from evaluation.prepare_asvspoof2019_la import read_protocol


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "data" / "datasets" / "asvspoof2019" / "LA.zip"
EXPECTED_ARCHIVE_SHA256 = (
    "208a7e4e3913f8c75ae1afd19bf32a5b29ae68435e9e30e23e5e98b6a155e4ec"
)
SPLIT_CONFIG = {
    "development": (
        "ASVspoof2019.LA.cm.dev.trl.txt",
        "/ASVspoof2019_LA_dev/flac/",
    ),
    "test": (
        "ASVspoof2019.LA.cm.eval.trl.txt",
        "/ASVspoof2019_LA_eval/flac/",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_unique_member(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected one ZIP member ending with {suffix!r}, found {len(matches)}")
    return matches[0]


def protocol_rows(archive: zipfile.ZipFile, split: str) -> tuple[list[dict], dict[str, str]]:
    protocol_name, audio_fragment = SPLIT_CONFIG[split]
    names = archive.namelist()
    protocol_member = find_unique_member(names, "/" + protocol_name)
    protocol_text = archive.read(protocol_member).decode("utf-8")

    # Reuse the strict official-protocol parser without extracting the corpus.
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8") as stream:
        stream.write(protocol_text)
        stream.flush()
        rows = read_protocol(Path(stream.name))

    audio_members = {
        Path(name).stem: name
        for name in names
        if audio_fragment in name and name.endswith(".flac")
    }
    missing = [row["utterance_id"] for row in rows if row["utterance_id"] not in audio_members]
    if missing:
        raise FileNotFoundError(f"ZIP lacks {len(missing)} protocol audio files")
    return rows, audio_members


def select_balanced_rows(
    rows: list[dict], samples_per_class: int, seed: str
) -> list[dict]:
    """Return a deterministic random-like, class-balanced protocol subset."""
    if samples_per_class < 1:
        raise ValueError("samples_per_class must be positive")
    selected = []
    for label in ("bonafide", "spoof"):
        candidates = [row for row in rows if row["label"] == label]
        candidates.sort(
            key=lambda row: hashlib.sha256(
                f"{seed}:{row['utterance_id']}".encode("utf-8")
            ).digest()
        )
        if len(candidates) < samples_per_class:
            raise ValueError(
                f"requested {samples_per_class} {label} rows, only {len(candidates)} exist"
            )
        selected.extend(candidates[:samples_per_class])
    return sorted(selected, key=lambda row: row["line_number"])


def make_sample(split: str, row: dict, member: str, digest: str) -> dict:
    synthetic = row["label"] == "spoof"
    return {
        "sample_id": f"ASV19-LA-{split.upper()}-{row['utterance_id']}",
        "path": f"LA.zip!/{member}",
        "sha256": digest,
        "label": "synthetic" if synthetic else "genuine",
        "split": split,
        "group_id": f"speaker:{row['speaker_id']}",
        "media_type": "audio",
        "manipulation_type": (
            f"asvspoof2019_la_{row['attack_id'].lower()}" if synthetic else "none"
        ),
        "ground_truth": {
            "basis": "Official ASVspoof 2019 LA protocol label",
            "reference": f"{SPLIT_CONFIG[split][0]}:{row['line_number']}",
        },
        "source": "ASVspoof 2019 logical-access database",
        "terms": "Open Data Commons Attribution License 1.0",
        "transformation": "none; official FLAC decoded directly from verified ZIP",
        "archive_member": member,
    }


def load_journal(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    entries: dict[str, dict] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        entry = json.loads(line)
        sample_id = entry.get("sample", {}).get("sample_id")
        if not sample_id:
            raise ValueError(f"invalid journal entry at line {line_number}")
        entries[sample_id] = entry
    return entries


def append_journal(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for entry in entries:
            stream.write(json.dumps(entry, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_archive(
    archive_path: Path,
    split: str,
    manifest_path: Path,
    predictions_path: Path,
    journal_path: Path,
    batch_size: int,
    limit: int | None = None,
    verify_archive: bool = True,
    samples_per_class: int | None = None,
    sampling_seed: str = "pratyaksh-asvspoof-pilot-v1",
) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if verify_archive and sha256_file(archive_path) != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("ASVspoof 2019 LA archive checksum mismatch")

    completed = load_journal(journal_path)
    probe = AASISTProbe()
    with zipfile.ZipFile(archive_path) as archive:
        rows, audio_members = protocol_rows(archive, split)
        if samples_per_class is not None:
            rows = select_balanced_rows(rows, samples_per_class, sampling_seed)
        if limit is not None:
            rows = rows[:limit]
        pending = [
            row
            for row in rows
            if f"ASV19-LA-{split.upper()}-{row['utterance_id']}" not in completed
        ]
        for offset in range(0, len(pending), batch_size):
            batch_rows = pending[offset : offset + batch_size]
            started = time.perf_counter()
            prepared = []
            entries = []
            for row in batch_rows:
                member = audio_members[row["utterance_id"]]
                raw = archive.read(member)
                digest = hashlib.sha256(raw).hexdigest()
                sample = make_sample(split, row, member, digest)
                try:
                    samples, decoded = decode_audio(raw)
                    prepared.append((sample, decoded, samples))
                except Exception as exc:
                    entries.append(
                        {
                            "sample": sample,
                            "prediction": {
                                "sample_id": sample["sample_id"],
                                "execution_status": "failed",
                                "error": f"{type(exc).__name__}: {exc}",
                                "model_id": MODEL_ID,
                                "model_revision": REVISION,
                                "preprocessing_version": PREPROCESSING_VERSION,
                            },
                        }
                    )
            if prepared:
                try:
                    outputs = probe.predict_batch_samples(
                        [item[2] for item in prepared]
                    )
                    for (sample, decoded, _), output in zip(prepared, outputs):
                        entries.append(
                            {
                                "sample": sample,
                                "prediction": {
                                    "sample_id": sample["sample_id"],
                                    "execution_status": "completed",
                                    "deepfake_score": output["spoof_score"],
                                    "input_sha256": sample["sha256"],
                                    "decoded_duration_ms": decoded["decoded_duration_ms"],
                                    "sample_rate_hz": decoded["sample_rate_hz"],
                                    "model_id": MODEL_ID,
                                    "model_revision": REVISION,
                                    "preprocessing_version": PREPROCESSING_VERSION,
                                },
                            }
                        )
                except Exception as exc:
                    for sample, _, _ in prepared:
                        entries.append(
                            {
                                "sample": sample,
                                "prediction": {
                                    "sample_id": sample["sample_id"],
                                    "execution_status": "failed",
                                    "error": f"{type(exc).__name__}: {exc}",
                                    "model_id": MODEL_ID,
                                    "model_revision": REVISION,
                                    "preprocessing_version": PREPROCESSING_VERSION,
                                },
                            }
                        )
            runtime_ms = round((time.perf_counter() - started) * 1000)
            for entry in entries:
                entry["prediction"]["batch_runtime_ms"] = runtime_ms
            append_journal(journal_path, entries)
            completed.update({entry["sample"]["sample_id"]: entry for entry in entries})
            print(
                json.dumps(
                    {
                        "split": split,
                        "completed": len(completed),
                        "requested": len(rows),
                        "last_batch_runtime_ms": runtime_ms,
                    }
                ),
                flush=True,
            )

    ordered = [
        completed[f"ASV19-LA-{split.upper()}-{row['utterance_id']}"]
        for row in rows
    ]
    manifest = {
        "schema_version": "1.1",
        "name": f"ASVspoof 2019 LA official {split} split",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples": [entry["sample"] for entry in ordered],
        "sampling": (
            {
                "method": "deterministic SHA-256 ordering within each class",
                "samples_per_class": samples_per_class,
                "seed": sampling_seed,
            }
            if samples_per_class is not None
            else {"method": "complete official split"}
        ),
    }
    validate_manifest(manifest)
    predictions = [entry["prediction"] for entry in ordered]
    atomic_json(manifest_path, manifest)
    atomic_json(predictions_path, predictions)
    return {
        "split": split,
        "sample_count": len(ordered),
        "completed_predictions": sum(
            item["execution_status"] == "completed" for item in predictions
        ),
        "manifest": str(manifest_path),
        "predictions": str(predictions_path),
        "journal": str(journal_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--split", choices=tuple(SPLIT_CONFIG), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Inference batch size; 1 is fastest on the supported Apple CPU setup.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--samples-per-class", type=int)
    parser.add_argument(
        "--sampling-seed", default="pratyaksh-asvspoof-pilot-v1"
    )
    parser.add_argument(
        "--skip-archive-checksum",
        action="store_true",
        help="Only for tests or an incomplete local smoke fixture.",
    )
    args = parser.parse_args()
    result = run_archive(
        args.archive,
        args.split,
        args.manifest,
        args.predictions,
        args.journal,
        args.batch_size,
        args.limit,
        not args.skip_archive_checksum,
        args.samples_per_class,
        args.sampling_seed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
