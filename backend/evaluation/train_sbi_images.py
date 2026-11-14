"""Audit still-image splits and fine-tune the local SBI pilot classification head."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn

from evaluation.evaluate_predictions import score_predictions, select_threshold
from face_forgery_detector import FaceForgeryDetector, PREPROCESSING_VERSION


class PerceptualIndex:
    """BK tree for exhaustive Hamming-distance queries of 64-bit dHashes."""

    def __init__(self):
        self.root = None

    def add_and_find(self, value, sample_index, radius=3):
        if self.root is None:
            self.root = (value, sample_index, {})
            return []
        matches = []
        pending = [self.root]
        while pending:
            stored, index, children = pending.pop()
            distance = (value ^ stored).bit_count()
            if distance <= radius:
                matches.append(index)
            pending.extend(child for edge, child in children.items()
                           if distance - radius <= edge <= distance + radius)
        node = self.root
        while True:
            stored, _, children = node
            distance = (value ^ stored).bit_count()
            if distance == 0:
                return matches
            if distance not in children:
                children[distance] = (value, sample_index, {})
                return matches
            node = children[distance]


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def audit_dataset(root, output, seed, train_per_class, evaluation_per_class):
    records = []
    unreadable = []
    parents = []

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def join(left, right):
        parents[find(left)] = find(right)

    by_bytes = {}
    by_pixels = {}
    perceptual = PerceptualIndex()
    original_counts = Counter()
    for split in ("Test", "Validation", "Train"):
        for label in ("Real", "Fake"):
            for path in sorted((root / split / label).glob("*.jpg")):
                relative = path.relative_to(root).as_posix()
                original_counts[split + "/" + label] += 1
                raw = path.read_bytes()
                image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    unreadable.append(relative)
                    continue
                byte_hash = hashlib.sha256(raw).hexdigest()
                pixel_hash = hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                thumb = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
                dhash = int.from_bytes(np.packbits(thumb[:, 1:] > thumb[:, :-1]).tobytes(), "big")
                index = len(records)
                parents.append(index)
                records.append({"path": relative, "sha256": byte_hash, "split": split,
                                "label": label, "dhash": f"{dhash:016x}"})
                for lookup, key in ((by_bytes, byte_hash), (by_pixels, pixel_hash)):
                    if key in lookup:
                        join(index, lookup[key])
                    else:
                        lookup[key] = index
                for other in perceptual.add_and_find(dhash, index):
                    join(index, other)
                if len(records) % 10000 == 0:
                    print("Audited", len(records), "images", flush=True)

    groups = defaultdict(list)
    for index in range(len(records)):
        groups[find(index)].append(index)
    clean = defaultdict(list)
    conflicts = 0
    excluded_cross_split = 0
    duplicate_images = 0
    for indices in groups.values():
        entries = [records[index] for index in indices]
        splits = {entry["split"] for entry in entries}
        if len({entry["label"] for entry in entries}) > 1:
            conflicts += len(entries)
            continue
        # Entire groups spanning splits are excluded to avoid choosing a split using outcomes.
        if len(splits) > 1:
            excluded_cross_split += len(entries)
            continue
        chosen = entries[0]
        duplicate_images += len(entries) - 1
        clean[chosen["split"] + "/" + chosen["label"]].append(chosen)

    rng = random.Random(seed)
    samples = []
    for folder, split in (("Train", "train"), ("Validation", "development"), ("Test", "test")):
        limit = train_per_class if split == "train" else evaluation_per_class
        for label in ("Real", "Fake"):
            pool = clean[folder + "/" + label]
            if len(pool) < limit:
                raise ValueError(f"{folder}/{label} has only {len(pool)} clean images, requested {limit}")
            for entry in rng.sample(pool, limit):
                samples.append({
                    "sample_id": entry["path"], "path": entry["path"], "sha256": entry["sha256"],
                    "split": split, "label": "genuine" if label == "Real" else "synthetic",
                    "group_id": entry["sha256"],
                    "manipulation_type": "none" if label == "Real" else "dataset_fake_unspecified",
                })
    audit = {
        "source_root": str(root), "original_counts": dict(original_counts),
        "unreadable": unreadable, "conflicting_label_group_images_excluded": conflicts,
        "cross_split_group_images_excluded": excluded_cross_split,
        "within_split_duplicate_images_excluded": duplicate_images,
        "clean_pool_counts": {key: len(value) for key, value in clean.items()},
        "method": "Connected groups using exact byte hash, decoded-pixel hash, and 64-bit dHash distance <= 3. Exclude conflicting labels and all groups spanning splits; keep one representative of other groups.",
        "limitations": [
            "dHash is a similarity heuristic and cannot guarantee removal of all related images.",
            "Identity and source-image annotations are unavailable; identity independence is unverified.",
            "Labels are inherited from the downloaded folders; generation methods are unverified.",
        ],
    }
    save_json(output / "audit.json", audit)
    save_json(output / "manifest.json", {"seed": seed, "samples": samples})
    print("Clean pools", audit["clean_pool_counts"], flush=True)
    return samples, audit


def extract_features(root, output, split, samples, detector, model, device):
    cache = output / (split + "-features.pt")
    if cache.exists():
        payload = torch.load(cache, map_location="cpu", weights_only=True)
        return payload["features"], payload["samples"], payload["unavailable"]
    selected = [sample for sample in samples if sample["split"] == split]
    features, kept, unavailable = [], [], []
    crops, batch_samples = [], []

    def flush():
        if not crops:
            return
        batch = torch.stack(crops).to(device).float() / 255
        with torch.inference_mode():
            pooled = model._avg_pooling(model.extract_features(batch)).flatten(1).cpu()
        features.extend(pooled.unbind())
        kept.extend(batch_samples)
        crops.clear()
        batch_samples.clear()

    for index, sample in enumerate(selected, 1):
        path = root / sample["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]:
            raise ValueError(f"Dataset changed after audit: {sample['path']}")
        with Image.open(path) as image:
            faces, _, _ = detector.crop_faces(ImageOps.exif_transpose(image))
        if len(faces) == 1:
            crops.append(torch.from_numpy(faces[0].transpose(2, 0, 1).copy()))
            batch_samples.append(sample)
            if len(crops) == 8:
                flush()
        else:
            unavailable.append({"sample_id": sample["sample_id"], "face_count": len(faces)})
        if index % 250 == 0:
            print(split, index, "/", len(selected), "images prepared", flush=True)
    flush()
    if not features:
        raise ValueError(f"No eligible faces in {split}")
    matrix = torch.stack(features)
    torch.save({"features": matrix, "samples": kept, "unavailable": unavailable}, cache)
    return matrix, kept, unavailable


def predict(head, features, samples, device):
    head.eval()
    with torch.inference_mode():
        scores = torch.cat([head(batch.to(device)).softmax(1)[:, 1].cpu()
                            for batch in features.split(256)]).tolist()
    return [{"sample_id": sample["sample_id"], "execution_status": "completed", "deepfake_score": score}
            for sample, score in zip(samples, scores, strict=True)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-per-class", type=int, default=3000)
    parser.add_argument("--evaluation-per-class", type=int, default=500)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    args = parser.parse_args()
    if min(args.train_per_class, args.evaluation_per_class, args.epochs) < 1:
        parser.error("Counts must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "report.json").exists():
        parser.error("Completed output already exists")
    cv2.setNumThreads(1)
    torch.set_num_threads(2)
    seed = 20261112
    torch.manual_seed(seed)
    protocol = {
        "seed": seed, "dataset": str(args.dataset.resolve()), "train_per_class": args.train_per_class,
        "evaluation_per_class": args.evaluation_per_class, "epochs": args.epochs,
        "preprocessing": PREPROCESSING_VERSION, "device": args.device,
        "training": "Freeze the current SBI pilot backbone; fit a normalized 128-unit MLP head on clean still-image training samples.",
        "selection": "Choose epoch and cutoff using development balanced accuracy only, before evaluating the reserved test sample.",
    }
    protocol_path = args.output / "protocol.json"
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise ValueError("Existing output has a different protocol")
    save_json(protocol_path, protocol)
    shutil.copyfile(__file__, args.output / "run-training.py")
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists():
        samples = json.loads(manifest_path.read_text())["samples"]
        audit = json.loads((args.output / "audit.json").read_text())
    else:
        samples, audit = audit_dataset(args.dataset, args.output, seed,
                                      args.train_per_class, args.evaluation_per_class)
    detector = FaceForgeryDetector(use_pilot=True)
    detector._load()
    model = detector.classifier.to(args.device).eval().requires_grad_(False)
    source_manifest = dict(detector.manifest)
    train_x, train_samples, train_skips = extract_features(
        args.dataset, args.output, "train", samples, detector, model, args.device)
    dev_x, dev_samples, dev_skips = extract_features(
        args.dataset, args.output, "development", samples, detector, model, args.device)
    labels = torch.tensor([sample["label"] == "synthetic" for sample in train_samples], dtype=torch.long)
    mean = train_x.mean(0)
    std = train_x.std(0).clamp_min(0.01)
    normalized_train = (train_x - mean) / std
    normalized_dev = (dev_x - mean) / std
    baseline_dev = predict(model._fc, dev_x, dev_samples, args.device)
    baseline_threshold = select_threshold(dev_samples, baseline_dev)["threshold"]
    head = nn.Sequential(nn.Linear(train_x.shape[1], 128), nn.GELU(), nn.Dropout(0.35),
                         nn.Linear(128, 2)).to(args.device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.0003, weight_decay=0.01)
    class_counts = torch.bincount(labels, minlength=2)
    if (class_counts == 0).any():
        raise ValueError("Training needs both classes with eligible faces")
    weights = class_counts.sum() / (2 * class_counts.float())
    criterion = nn.CrossEntropyLoss(weight=weights.to(args.device))
    best_value = -1
    history = []
    for epoch in range(1, args.epochs + 1):
        head.train()
        for indices in torch.randperm(len(labels)).split(64):
            optimizer.zero_grad()
            loss = criterion(head(normalized_train[indices].to(args.device)),
                             labels[indices].to(args.device))
            loss.backward()
            optimizer.step()
        predictions = predict(head, normalized_dev, dev_samples, args.device)
        selection = select_threshold(dev_samples, predictions)
        accuracy = selection["selection_metrics"]["objective_value"]
        history.append({"epoch": epoch, "development_balanced_accuracy": accuracy,
                        "threshold": selection["threshold"]})
        print("Epoch", epoch, "development balanced accuracy", round(accuracy, 4), flush=True)
        if accuracy > best_value:
            best_value = accuracy
            best_state = {key: value.detach().cpu().clone() for key, value in head.state_dict().items()}
            best_epoch, best_threshold = epoch, selection["threshold"]
            save_json(args.output / "selection.json", {
                "epoch": best_epoch, "threshold": best_threshold,
                "development_balanced_accuracy": best_value,
                "baseline_development_threshold": baseline_threshold,
            })
    head.load_state_dict(best_state)
    save_json(args.output / "history.json", history)
    checkpoint_path = args.output / "sbi-still-image-head.pt"
    torch.save({"head": best_state, "mean": mean, "std": std, "source": source_manifest,
                "preprocessing": PREPROCESSING_VERSION, "threshold": best_threshold}, checkpoint_path)
    # Selection and checkpoint are saved before test features are read.
    test_x, test_samples, test_skips = extract_features(
        args.dataset, args.output, "test", samples, detector, model, args.device)
    reports = {}
    for name, classifier, features, threshold in (
        ("previous_pilot_fixed_cutoff", model._fc, test_x, 0.03699474409222603),
        ("previous_pilot_development_cutoff", model._fc, test_x, baseline_threshold),
        ("fine_tuned_head", head, (test_x - mean) / std, best_threshold),
    ):
        predictions = predict(classifier, features, test_samples, args.device)
        missing = [{"sample_id": row["sample_id"], "execution_status": "unsupported"}
                   for row in test_skips]
        reports[name] = score_predictions([s for s in samples if s["split"] == "test"],
                                          predictions + missing, threshold, "test")
        save_json(args.output / (name + "-predictions.json"), predictions + missing)
    report = {
        "source": source_manifest, "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        "selected_epoch": best_epoch, "threshold": best_threshold,
        "eligible_face_crops": {"train": len(train_samples), "development": len(dev_samples), "test": len(test_samples)},
        "images_without_one_eligible_face": {"train": train_skips, "development": dev_skips, "test": test_skips},
        "metrics": reports, "limitations": audit["limitations"],
    }
    save_json(args.output / "report.json", report)
    for name, result in reports.items():
        print(name, result["confusion_matrix"], result["metrics"], flush=True)
    print("Saved", args.output, flush=True)


if __name__ == "__main__":
    main()
