"""Fine-tune the last two SBI blocks using an existing cleaned still-image run."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

import cv2
import torch
from PIL import Image, ImageOps
from torch import nn

from evaluation.evaluate_predictions import score_predictions, select_threshold
from evaluation.train_sbi_images import save_json
from face_forgery_detector import FaceForgeryDetector, PREPROCESSING_VERSION


def prepare_prefix(root, source_run, output, split, detector, model, device):
    cache = output / (split + "-prefix.pt")
    if cache.exists():
        return torch.load(cache, map_location="cpu", weights_only=True)
    original = torch.load(source_run / (split + "-features.pt"), map_location="cpu", weights_only=True)
    samples = original["samples"]
    matrix, crops = [], []
    def flush():
        if not crops:
            return
        with torch.inference_mode():
            x = model._swish(model._bn0(model._conv_stem(torch.stack(crops).to(device).float() / 255)))
            for layer in list(model._blocks)[:-2]:
                x = layer(x)
            matrix.extend(x.cpu().unbind())
        crops.clear()
    for index, sample in enumerate(samples, 1):
        path = root / sample["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]:
            raise ValueError("Image changed after the original audit")
        with Image.open(path) as image:
            faces, _, _ = detector.crop_faces(ImageOps.exif_transpose(image))
        if len(faces) != 1:
            raise ValueError("Face extraction changed since the previous run")
        crops.append(torch.from_numpy(faces[0].transpose(2, 0, 1).copy()))
        if len(crops) == 8:
            flush()
        if index % 250 == 0:
            print(split, index, "/", len(samples), "prefix features prepared", flush=True)
    flush()
    payload = {"features": torch.stack(matrix), "samples": samples,
               "unavailable": original["unavailable"]}
    torch.save(payload, cache)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("Epochs must be positive")
    if args.output.exists():
        parser.error("Use a fresh output folder")
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output / "run-training.py")
    previous = json.loads((args.source_run / "protocol.json").read_text())
    root = Path(previous["dataset"])
    save_json(args.output / "protocol.json", {
        "source_run": str(args.source_run.resolve()), "dataset": str(root),
        "seed": 20261112, "epochs": args.epochs, "device": args.device,
        "backbone_learning_rate": 0.000015, "head_learning_rate": 0.0001,
        "batch_size": 8, "preprocessing": PREPROCESSING_VERSION,
        "selection": "Development balanced accuracy, including the starting checkpoint at epoch zero. Stop after three epochs without improvement.",
        "test": "Same reserved sample as the first still-image run. Repeated model comparisons reduce independence of the test estimate.",
        "cleanup": "Reuse the cleaned manifest and eligible faces from the first still-image run.",
    })
    torch.manual_seed(20261112)
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    device = args.device
    detector = FaceForgeryDetector(use_pilot=True)
    detector._load()
    model = detector.classifier.to(device).eval().requires_grad_(False)
    source_manifest = dict(detector.manifest)
    starting = torch.load(args.source_run / "sbi-still-image-head.pt", map_location="cpu", weights_only=True)
    if starting["source"] != source_manifest or starting["preprocessing"] != PREPROCESSING_VERSION:
        raise ValueError("Source checkpoint mismatch")
    mean, std = starting["mean"].to(device), starting["std"].to(device)
    head = nn.Sequential(nn.Linear(mean.numel(), 128), nn.GELU(), nn.Dropout(.35), nn.Linear(128, 2)).to(device)
    head.load_state_dict(starting["head"])
    block = nn.Sequential(*[copy.deepcopy(layer) for layer in model._blocks[-2:]]).to(device).eval().requires_grad_(True)

    def logits(features):
        x = block(features.to(device))
        x = model._swish(model._bn1(model._conv_head(x)))
        return head((model._avg_pooling(x).flatten(1) - mean) / std)

    def predict(payload):
        head.eval()
        with torch.no_grad():
            scores = torch.cat([logits(batch).softmax(1)[:, 1].cpu()
                                for batch in payload["features"].split(16)]).tolist()
        return [{"sample_id": sample["sample_id"], "execution_status": "completed", "deepfake_score": value}
                for sample, value in zip(payload["samples"], scores, strict=True)]

    train = prepare_prefix(root, args.source_run, args.output, "train", detector, model, device)
    dev = prepare_prefix(root, args.source_run, args.output, "development", detector, model, device)
    labels = torch.tensor([s["label"] == "synthetic" for s in train["samples"]], dtype=torch.long)
    counts = torch.bincount(labels, minlength=2).float()
    criterion = nn.CrossEntropyLoss(weight=(counts.sum() / (2 * counts)).to(device))
    optimizer = torch.optim.AdamW([
        {"params": block.parameters(), "lr": .000015},
        {"params": head.parameters(), "lr": .0001},
    ], weight_decay=.01)
    best_value = -1
    history = []
    checkpoint_path = args.output / "sbi-still-image-two-blocks.pt"
    for epoch in range(args.epochs + 1):
        if epoch:
            head.train()
            # Keep pretrained batch-normalization statistics fixed for these small batches.
            for step, indices in enumerate(torch.randperm(len(labels)).split(8), 1):
                optimizer.zero_grad()
                loss = criterion(logits(train["features"][indices]), labels[indices].to(device))
                loss.backward()
                optimizer.step()
                if step % 200 == 0:
                    print("Epoch", epoch, "training batch", step, flush=True)
        predictions = predict(dev)
        selection = select_threshold(dev["samples"], predictions)
        value = selection["selection_metrics"]["objective_value"]
        history.append({"epoch": epoch, "development_balanced_accuracy": value,
                        "threshold": selection["threshold"]})
        print("Epoch", epoch, "development balanced accuracy", value, flush=True)
        if value > best_value:
            best_value, best_epoch, threshold = value, epoch, selection["threshold"]
            torch.save({
                "last_two_blocks": {k: v.detach().cpu().clone() for k, v in block.state_dict().items()},
                "head": {k: v.detach().cpu().clone() for k, v in head.state_dict().items()},
                "mean": mean.cpu(), "std": std.cpu(), "source": source_manifest,
                "preprocessing": PREPROCESSING_VERSION, "threshold": threshold,
            }, checkpoint_path)
            save_json(args.output / "selection.json", {"epoch": epoch, "threshold": threshold,
                                                     "development_balanced_accuracy": value})
        save_json(args.output / "history.json", history)
        if epoch - best_epoch >= 3:
            print("Stopped after three epochs without validation improvement", flush=True)
            break

    best = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    block.load_state_dict(best["last_two_blocks"])
    head.load_state_dict(best["head"])
    test = prepare_prefix(root, args.source_run, args.output, "test", detector, model, device)
    predictions = predict(test)
    missing = [{"sample_id": row["sample_id"], "execution_status": "unsupported"}
               for row in test["unavailable"]]
    manifest = json.loads((args.source_run / "manifest.json").read_text())["samples"]
    metrics = score_predictions([s for s in manifest if s["split"] == "test"],
                                predictions + missing, threshold, "test")
    save_json(args.output / "test-predictions.json", predictions + missing)
    prior = json.loads((args.source_run / "report.json").read_text())
    report = {
        "selected_epoch": best_epoch, "threshold": threshold,
        "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        "eligible_face_crops": prior["eligible_face_crops"],
        "previous_head_test": prior["metrics"]["fine_tuned_head"], "fine_tuned_backbone_test": metrics,
        "limitations": [*prior["limitations"], "This test sample has now been used for more than one model comparison."],
    }
    save_json(args.output / "report.json", report)
    print(json.dumps({"selected_epoch": best_epoch, "test": metrics["metrics"],
                      "confusion_matrix": metrics["confusion_matrix"], "coverage": metrics["coverage"]}), flush=True)
    print("Saved", args.output, flush=True)


if __name__ == "__main__":
    main()
