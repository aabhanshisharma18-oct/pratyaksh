"""Research pilot for whole-image synthetic detection with a frozen CLIP encoder."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import random
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

from PIL import Image, ImageOps

import detector

DATASET = "TheKernel01/Tiny-GenImage"
REVISION = "89c4fe9efd0ebc7ce5c7641ef57d578ccd639c69"
HELD_OUT = "Midjourney"
SEED = 20261113
SERVER = "https://datasets-server.huggingface.co"
VARIANTS = ("original", "jpeg_edit", "screenshot_simulation")


def fetch(url):
    if urlparse(url).hostname != "datasets-server.huggingface.co":
        raise ValueError("Unexpected dataset asset host")
    for attempt in range(3):
        try:
            with urlopen(url, timeout=45) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise


def sample_rows(split, offset):
    query = urlencode(dict(dataset=DATASET, config="default", split=split, offset=offset, length=80))
    data = json.loads(fetch(f"{SERVER}/rows?{query}"))
    feature = {item["name"]: item["type"]["names"] for item in data["features"]
               if item["type"]["_type"] == "ClassLabel"}
    rows = []
    for item in data["rows"]:
        row = item["row"]
        label = feature["label"][row["label"]]
        generator = feature["generator"][row["generator"]]
        url = row["image"]["src"]
        if f"/{REVISION}/" not in url:
            raise ValueError("Dataset asset revision changed")
        if label not in {"real", "fake"} or (label == "real") != (generator == "Real"):
            raise ValueError("Unexpected label or generator")
        rows.append(dict(id=f"{split}-{item['row_idx']}", label=int(label == "fake"),
                         generator=generator, url=url))
    return rows


def load_image(path):
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def cache_image(row, cache):
    path = cache / (row["id"] + ".image")
    if not path.exists():
        path.write_bytes(fetch(row["url"]))
    image = load_image(path)
    tiny = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).tobytes()
    dhash = sum((tiny[y * 9 + x] > tiny[y * 9 + x + 1]) << (y * 8 + x)
                for y in range(8) for x in range(8))
    return {**row, "path":str(path), "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "pixel_sha256":hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest(),
            "dhash":dhash}


def prepare(cache):
    cache.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    jobs = [("train", offset) for offset in range(0, 640, 80)]
    jobs += [("validation", offset) for offset in range(0, 800, 80)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        pools = {"train":[], "validation":[]}
        for job, rows in zip(jobs, pool.map(lambda job: sample_rows(*job), jobs)):
            pools[job[0]].extend(rows)
        candidates = [row for row in pools["train"] if row["generator"] != HELD_OUT]
        tests = [row for row in pools["validation"] if row["generator"] == HELD_OUT]
        real_tests = [row for row in pools["validation"] if row["label"] == 0]
        rng.shuffle(real_tests)
        candidates += tests + real_tests[:len(tests) + 20]
        decoded = list(pool.map(lambda row: cache_image(row, cache), candidates))
    # Keep a single representative across all splits for duplicate and near-duplicate clusters.
    # Give the test pool priority; every derived variant stays with its base image.
    accepted = []
    seen = []
    for row in sorted(decoded, key=lambda row: not row["id"].startswith("validation")):
        duplicate = any(row["pixel_sha256"] == prior["pixel_sha256"] or
                        (row["dhash"] ^ prior["dhash"]).bit_count() <= 3 for prior in seen)
        seen.append(row)
        if not duplicate:
            accepted.append(row)
    train_pool = [row for row in accepted if row["id"].startswith("train")]
    test_pool = [row for row in accepted if row["id"].startswith("validation")]
    rng.shuffle(train_pool)
    rng.shuffle(test_pool)
    partitions = {"train":[], "development":[], "test":[]}
    test_count = min(48, *(sum(row["label"] == label for row in test_pool) for label in (0, 1)))
    for label in (0, 1):
        selected = [row for row in train_pool if row["label"] == label]
        partitions["train"] += selected[:112]
        partitions["development"] += selected[112:144]
        partitions["test"] += [row for row in test_pool if row["label"] == label][:test_count]
    for split, rows in partitions.items():
        if len(rows) < 20 or {row["label"] for row in rows} != {0, 1}:
            raise ValueError(f"Insufficient labeled data for {split}")
        print(split, len(rows), dict(Counter(row["generator"] for row in rows)), flush=True)
    print("Excluded duplicate/near-duplicate candidates:", len(decoded) - len(accepted), flush=True)
    return partitions


def variants(image):
    yield "original", image
    reduced = image.copy()
    reduced.thumbnail((480, 480), Image.Resampling.LANCZOS)
    payload = io.BytesIO()
    reduced.save(payload, "JPEG", quality=55)
    with Image.open(payload) as edited:
        yield "jpeg_edit", edited.convert("RGB")
    inset = ImageOps.contain(image, (290, 230))
    canvas = Image.new("RGB", (350, 300), "#dce3ea")
    canvas.paste(inset, ((350-inset.width)//2, (300-inset.height)//2+16))
    yield "screenshot_simulation", canvas


def encode(rows, model, device, batch_size, torch, split):
    features, metadata, errors, tensors = [], [], [], []
    planned = []
    for row in rows:
        planned.extend({**row, "variant":variant} for variant in VARIANTS)

    def flush():
        if tensors:
            with torch.inference_mode():
                batch = torch.stack(tensors).to(device)
                features.append(model.backbone.encode_image(batch).float().cpu())
            tensors.clear()

    for index, row in enumerate(rows, 1):
        try:
            transformed = [(name, model._official_eval_preprocess(image))
                           for name, image in variants(load_image(row["path"]))]
        except (OSError, ValueError) as error:
            errors.append({"id":row["id"], "error":str(error)})
            continue
        for variant, tensor in transformed:
            metadata.append({**row, "variant":variant})
            tensors.append(tensor)
            if len(tensors) == batch_size:
                flush()
        if index % 25 == 0:
            print(f"{split}: encoded {index}/{len(rows)} sources", flush=True)
    flush()
    if not features:
        raise ValueError(f"No usable features for {split}")
    return torch.cat(features), metadata, planned, errors


def metrics(rows, scores, threshold):
    tp = tn = fp = fn = 0
    for row, score in zip(rows, scores, strict=True):
        positive = score >= threshold
        tp += int(row["label"] == 1 and positive)
        fn += int(row["label"] == 1 and not positive)
        fp += int(row["label"] == 0 and positive)
        tn += int(row["label"] == 0 and not positive)
    recall = tp/(tp+fn) if tp+fn else None
    specificity = tn/(tn+fp) if tn+fp else None
    return dict(tp=tp, tn=tn, fp=fp, fn=fn, scored=len(rows),
                accuracy=(tp+tn)/len(rows) if rows else None,
                recall=recall, false_positive_rate=1-specificity if specificity is not None else None,
                balanced_accuracy=(recall+specificity)/2 if recall is not None and specificity is not None else None)


def choose_threshold(rows, scores):
    candidates = sorted(set(scores))
    candidates.append(float("inf"))
    def objective(cutoff):
        result = metrics(rows, scores, cutoff)
        return result["balanced_accuracy"], -result["false_positive_rate"]
    threshold = max(candidates, key=objective)
    return threshold if threshold != float("inf") else 1.000001


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu","mps"], default="cpu")
    args = parser.parse_args()
    import torch
    import torch.nn.functional as F

    torch.manual_seed(SEED)
    torch.set_num_threads(4)
    args.output.mkdir(parents=True, exist_ok=False)
    partitions = prepare(args.cache)
    protocol = dict(dataset=DATASET, revision=REVISION, seed=SEED, license="CC BY-NC-SA 4.0 (dataset card)",
                    held_out_generator=HELD_OUT, variants=VARIANTS,
                    preprocessing="Official UFD center crop 224 and CLIP normalization",
                    source_policy="Dataset image is the source group; exact pixel and dHash <=3 duplicates suppressed across splits. Prompt and capture identity are unavailable.",
                    threshold_policy="Each head maximizes development balanced accuracy; ties favor fewer false positives.",
                    classifier="L2-normalized frozen CLIP features, Linear(768,1), BCE, L2 weight penalty, 200 full-batch Adam steps, lr 0.015")
    (args.output/"protocol.json").write_text(json.dumps(protocol,indent=2))
    (args.output/"manifest.json").write_text(json.dumps(partitions,indent=2))
    model = detector.ImageDetector()
    model._load()
    model.backbone.requires_grad_(False).to(args.device)
    print("Verified and loaded frozen CLIP checkpoint", flush=True)
    def run_split(name):
        return encode(partitions[name],model,args.device,8,torch,name)
    x_train, train, train_planned, train_errors = run_split("train")
    x_dev, dev, dev_planned, dev_errors = run_split("development")
    head = torch.nn.Linear(768,1)
    x = F.normalize(x_train)
    y = torch.tensor([row["label"] for row in train],dtype=torch.float32)
    optimizer = torch.optim.Adam(head.parameters(),lr=.015)
    for _ in range(200):
        optimizer.zero_grad()
        loss = F.binary_cross_entropy_with_logits(head(x).flatten(),y) + .0001*head.weight.square().sum()
        loss.backward()
        optimizer.step()

    @torch.no_grad()
    def scores(features):
        return {
            "universal_fake_detect":model.head(features).sigmoid().flatten().tolist(),
            "pratyaksh_clip_head":head(F.normalize(features)).sigmoid().flatten().tolist(),
        }

    dev_scores = scores(x_dev)
    thresholds = {key:choose_threshold(dev,values) for key,values in dev_scores.items()}
    checkpoint = args.output/"clip-linear-head.pt"
    torch.save(head.state_dict(),checkpoint)
    (args.output/"selection.json").write_text(json.dumps(thresholds,indent=2))
    print("Froze checkpoint and thresholds before test:", thresholds, flush=True)
    x_test, test, planned, test_errors = run_split("test")
    test_scores = scores(x_test)
    evaluation = {}
    for key, values in test_scores.items():
        threshold = thresholds[key]
        per_variant = {}
        for variant in VARIANTS:
            subset = [(row,value) for row,value in zip(test,values) if row["variant"] == variant]
            per_variant[variant] = metrics([pair[0] for pair in subset],[pair[1] for pair in subset],threshold)
        evaluation[key] = dict(threshold=threshold, overall=metrics(test,values,threshold), by_variant=per_variant)
    predictions = [dict(id=row["id"],variant=row["variant"],label=row["label"],generator=row["generator"],
                        **{name:values[index] for name,values in test_scores.items()})
                   for index,row in enumerate(test)]
    report = dict(protocol=protocol, baseline=model.manifest,
                  head_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                  source_counts={key:len(rows) for key,rows in partitions.items()},
                  coverage={"train":[len(train),len(train_planned)],"development":[len(dev),len(dev_planned)],
                            "test":[len(test),len(planned)]}, errors=train_errors+dev_errors+test_errors,
                  development={key:metrics(dev,values,thresholds[key]) for key,values in dev_scores.items()},
                  test=evaluation)
    (args.output/"predictions.json").write_text(json.dumps(predictions,indent=2))
    (args.output/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report["test"],indent=2),flush=True)


if __name__ == "__main__":
    main()
