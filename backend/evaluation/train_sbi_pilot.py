"""Fine-tune the pretrained SBI classification head on a local Celeb-DF v2 pilot."""

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

import cv2
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from evaluation.evaluate_predictions import score_predictions, select_threshold
from face_forgery_detector import FaceForgeryDetector, PREPROCESSING_VERSION


def build_splits(root, limit, rng, test_pool):
    official_test = set()
    for line in (root / "List_of_testing_videos.txt").read_text().splitlines():
        if line.strip():
            official_test.add(line.split(maxsplit=1)[1])
    originals = sorted((root / "Celeb-real").glob("*.mp4"))
    identities = sorted({path.stem.split("_")[0] for path in originals})
    rng.shuffle(identities)
    partitions = {
        "train": set(identities[20:]),
        "development": set(identities[:10]),
        "test": set(identities[10:20]),
    }
    candidates = [(path, 0) for path in originals]
    candidates.extend((path, 1) for path in sorted((root / "Celeb-synthesis").glob("*.mp4")))
    splits = {}
    for split, allowed in partitions.items():
        by_label = [[], []]
        for path, label in candidates:
            people = set(re.findall(r"id\d+", path.stem))
            in_official_test = path.relative_to(root).as_posix() in official_test
            eligible = (
                in_official_test == (split == "test")
                if test_pool == "official"
                else split == "test" or not in_official_test
            )
            if people and people <= allowed and eligible:
                by_label[label].append((path, label))
        count = min(limit, *(len(entries) for entries in by_label))
        if not count:
            raise ValueError(f"{split} has no balanced set of eligible videos")
        splits[split] = [entry for entries in by_label for entry in rng.sample(entries, count)]
    return splits, {split: sorted(people) for split, people in partitions.items()}


def sample_faces(path, count, detector):
    capture = cv2.VideoCapture(str(path))
    try:
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        for index in range(min(frames, count)):
            position = (2 * index + 1) * frames // (2 * min(frames, count))
            capture.set(cv2.CAP_PROP_POS_FRAMES, position)
            ok, frame = capture.read()
            if ok:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                crops, _, _ = detector.crop_faces(image)
                if len(crops) == 1:
                    yield torch.from_numpy(crops[0].transpose(2, 0, 1).copy()), position
    finally:
        capture.release()


def prepare(root, split, videos, detector, frames, feature_device, feature_model):
    features, labels, samples, skipped = [], [], [], []
    for path, label in videos:
        items = list(sample_faces(path, frames, detector))
        relative = path.relative_to(root).as_posix()
        if not items:
            skipped.append(relative)
            continue
        batch = torch.stack([crop for crop, _ in items]).to(feature_device).float() / 255
        with torch.no_grad():
            pooled = feature_model._avg_pooling(feature_model.extract_features(batch)).flatten(1).cpu()
        features.extend(pooled.unbind())
        labels.extend([label] * len(items))
        samples.extend(
            {
                "sample_id": f"{relative}#{position}",
                "split": split,
                "label": "synthetic" if label else "genuine",
                "group_id": relative,
                "manipulation_type": "face_swap" if label else "none",
            }
            for _, position in items
        )
    if len(set(labels)) != 2:
        raise ValueError(f"{split} must have detected face crops from both classes")
    print(f"{split}: {dict(Counter(labels))} face crops (0 genuine, 1 manipulated), "
          f"{len(skipped)} videos without an eligible crop", flush=True)
    return TensorDataset(torch.stack(features), torch.tensor(labels)), samples, skipped


def measure(head, dataset, samples, device):
    with torch.no_grad():
        scores = head(dataset.tensors[0].to(device)).softmax(1)[:, 1].cpu().tolist()
    return [
        {"sample_id": sample["sample_id"], "execution_status": "completed", "deepfake_score": score}
        for sample, score in zip(samples, scores)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--videos-per-class", type=int, default=24)
    parser.add_argument("--frames-per-video", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--test-pool", choices=("official", "identity"), default="official",
                        help="Use official test clips only, or all clips from reserved identities.")
    args = parser.parse_args()
    if min(args.videos_per_class, args.frames_per_video, args.epochs) < 1:
        parser.error("Counts must be positive")
    if args.device == "mps" and not torch.backends.mps.is_available():
        parser.error("MPS is unavailable. Use --device cpu.")
    if args.output.exists():
        parser.error("Choose a new output directory for this run.")
    torch.manual_seed(42)
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    splits, identities = build_splits(args.dataset, args.videos_per_class, random.Random(42), args.test_pool)
    print("Selected videos:", {split: len(videos) for split, videos in splits.items()}, flush=True)
    detector = FaceForgeryDetector()
    detector._load()
    model = detector.classifier.to(args.device)
    baseline = nn.Linear(model._fc.in_features, 2).to(args.device)
    baseline.load_state_dict(model._fc.state_dict())
    head = nn.Linear(model._fc.in_features, 2).to(args.device)
    head.load_state_dict(baseline.state_dict())
    train, _, train_skipped = prepare(args.dataset, "train", splits["train"], detector, args.frames_per_video, args.device, model)
    dev, dev_samples, dev_skipped = prepare(args.dataset, "development", splits["development"], detector, args.frames_per_video, args.device, model)
    baseline_threshold = select_threshold(dev_samples, measure(baseline, dev, dev_samples, args.device))
    optimizer = torch.optim.AdamW(head.parameters(), lr=1e-4)
    loss_fn = nn.CrossEntropyLoss()
    best_value = -1
    for epoch in range(args.epochs):
        for features, labels in DataLoader(train, batch_size=8, shuffle=True):
            optimizer.zero_grad()
            loss = loss_fn(head(features.to(args.device)), labels.to(args.device))
            loss.backward()
            optimizer.step()
        selection = select_threshold(dev_samples, measure(head, dev, dev_samples, args.device))
        value = selection["selection_metrics"]["objective_value"]
        print(f"Epoch {epoch + 1}: development balanced accuracy {value:.3f}", flush=True)
        if value > best_value:
            best_value = value
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in head.state_dict().items()}
            best_threshold = selection
    head.load_state_dict(best_state)
    args.output.mkdir(parents=True)
    thresholds = {"pretrained": baseline_threshold, "fine_tuned": best_threshold}
    (args.output / "thresholds.json").write_text(json.dumps(thresholds, indent=2))
    model._fc.load_state_dict(best_state)
    torch.save({"model": {name: tensor.detach().cpu() for name, tensor in model.state_dict().items()},
                "source": detector.manifest, "preprocessing": PREPROCESSING_VERSION}, args.output / "sbi-celeb-pilot.pt")
    test, test_samples, test_skipped = prepare(args.dataset, "test", splits["test"], detector, args.frames_per_video, args.device, model)
    metrics = {}
    for name, classifier in (("pretrained", baseline), ("fine_tuned", head)):
        predictions = measure(classifier, test, test_samples, args.device)
        metrics[name] = score_predictions(test_samples, predictions, thresholds[name]["threshold"], "test")
        (args.output / f"{name}-predictions.json").write_text(json.dumps(predictions, indent=2))
    report = {
        "protocol": "Face-crop pilot on disjoint groups of Celeb-DF identities",
        "test_pool": args.test_pool,
        "seed": 42,
        "frames_per_video": args.frames_per_video,
        "epochs": args.epochs,
        "identities": identities,
        "videos": {split: [path.relative_to(args.dataset).as_posix() for path, _ in entries] for split, entries in splits.items()},
        "videos_without_eligible_crops": {"train": train_skipped, "development": dev_skipped, "test": test_skipped},
        "frame_metrics": metrics,
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2))
    print(f"Saved checkpoint and report to {args.output}", flush=True)


if __name__ == "__main__":
    main()
