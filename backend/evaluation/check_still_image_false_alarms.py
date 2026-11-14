"""Compare fixed CLIP heads at development-selected low-false-alarm cutoffs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random

import torch
import torch.nn.functional as F

import detector
from evaluation.train_still_image_head import cache_image, encode, metrics, sample_rows


def cutoff_for_budget(rows, scores, budget):
    allowed = [cutoff for cutoff in {*scores, 1.000001}
               if metrics(rows, scores, cutoff)["false_positive_rate"] <= budget + 1e-10]
    return max(sorted(allowed), key=lambda cutoff: (
        metrics(rows, scores, cutoff)["recall"], -metrics(rows, scores, cutoff)["false_positive_rate"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    args.cache.mkdir(parents=True, exist_ok=True)
    prior = json.loads((args.prior / "manifest.json").read_text())
    torch.set_num_threads(4)
    rng = random.Random(701)
    with ThreadPoolExecutor(max_workers=12) as pool:
        candidates = [row for page in pool.map(lambda offset: sample_rows("validation", offset),
                                              range(800, 1280, 80)) for row in page]
        selected = []
        for generator, cap in (("Real", 45), ("Midjourney", 15), ("SD15", 15), ("BigGAN", 15)):
            group = [row for row in candidates if row["generator"] == generator]
            rng.shuffle(group)
            selected.extend(group[:cap+10])
        decoded = list(pool.map(lambda row: cache_image(row,args.cache), selected))
    seen = [row for split in prior.values() for row in split]
    fresh = []
    for row in decoded:
        cap = 45 if row["label"] == 0 else 15
        if sum(item["generator"] == row["generator"] for item in fresh) >= cap:
            continue
        if any(row["pixel_sha256"] == existing["pixel_sha256"] or
               (row["dhash"] ^ existing["dhash"]).bit_count() <= 3 for existing in seen):
            continue
        fresh.append(row)
        seen.append(row)
    counts = {g:sum(r["generator"]==g for r in fresh) for g in ("Real","Midjourney","SD15","BigGAN")}
    if min(counts.values()) < 5:
        raise ValueError(f"Insufficient fresh samples: {counts}")
    (args.output / "test-manifest.json").write_text(json.dumps(fresh,indent=2))
    print("Fresh source counts:",counts,flush=True)
    model = detector.ImageDetector()
    model._load()
    head = torch.nn.Linear(768, 1)
    head.load_state_dict(torch.load(args.prior / "clip-linear-head.pt", weights_only=True))
    head.eval()

    @torch.no_grad()
    def score(features):
        return {"baseline":model.head(features).sigmoid().flatten().tolist(),
                "pratyaksh":head(F.normalize(features)).sigmoid().flatten().tolist()}

    x, dev, _, _ = encode(prior["development"],model,"cpu",8,torch,"development")
    cutoffs = {key:cutoff_for_budget(dev,values,.10) for key,values in score(x).items()}
    (args.output / "selection.json").write_text(json.dumps(cutoffs,indent=2))
    print("Locked cutoffs:", cutoffs,flush=True)
    x, test, planned, errors = encode(fresh,model,"cpu",8,torch,"fresh test")
    old = json.loads((args.prior / "selection.json").read_text())
    results = {}
    for key, values in score(x).items():
        old_key = "universal_fake_detect" if key == "baseline" else "pratyaksh_clip_head"
        results[key] = {}
        for policy, threshold in (("previous",old[old_key]),("low_false_alarm",cutoffs[key])):
            breakdown = {}
            for variant in ("original","jpeg_edit","screenshot_simulation"):
                indices = [i for i,row in enumerate(test) if row["variant"]==variant]
                breakdown[variant] = metrics([test[i] for i in indices],[values[i] for i in indices],threshold)
            results[key][policy] = {
                "threshold":threshold,"overall":metrics(test,values,threshold),"by_variant":breakdown,
                "caught_by_generator": {
                    generator:metrics([row for row in test if row["generator"]==generator],
                                      [value for row,value in zip(test,values) if row["generator"]==generator],
                                      threshold)["tp"]
                    for generator in ("Midjourney","SD15","BigGAN")
                }
            }
    report = {"development_false_alarm_budget":.10,"test_source_counts":counts,
              "coverage":[len(test),len(planned)],"results":results,"errors":errors}
    (args.output / "report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
