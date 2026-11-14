"""Capture and score a source-separated benchmark for screenshot interface interference."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys

import cv2
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from provenance import compare_visual, prepare_visual


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def scene(seed, view=0):
    """Independent renders of the same scene layout, with changing texture and viewpoint."""
    rng = random.Random(seed * 97 + view)
    palette = [(54, 88, 119), (114, 83, 63), (76, 108, 82)]
    image = Image.new("RGB", (720, 520), palette[seed % len(palette)])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 374, 720, 520), fill=(178, 156, 132))
    x = 302 + 37 * view
    draw.polygon([(x-86, 230), (x+90, 230), (x+65, 390), (x-61, 390)], fill=(233, 224, 192))
    for _ in range(230):
        a, b = rng.randrange(10, 700), rng.randrange(12, 505)
        color = tuple(rng.randrange(25, 240) for _ in range(3))
        if rng.random() < .5:
            draw.line((a, b, a+rng.randrange(5, 42), b+rng.randrange(-20, 22)), fill=color, width=3)
        else:
            r = rng.randrange(2, 11)
            draw.ellipse((a-r,b-r,a+r,b+r), outline=color, width=2)
    return image


def wilson(k, n):
    if not n:
        return None
    z = 1.96
    p = k / n
    center = (p + z*z/(2*n))/(1+z*z/n)
    delta = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [round(max(0, center-delta), 4), round(min(1, center+delta), 4)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = []
    for seed in range(12):
        family = f"source-{seed:02}"
        original = scene(seed)
        original.save(out / f"{family}-original.png")
        original.crop((151, 98, 595, 414)).save(out / f"{family}-crop.png")
        original.save(out / f"{family}-compressed.jpg", quality=15)
        scene(seed, view=1).save(out / f"{family}-independent-render.png")
        sources.append({"family": family, "split": "development" if seed < 6 else "test",
                        "original": f"{family}-original.png", "screenshot": f"{family}-screenshot.png"})
    save_json(out / "sources.json", sources)
    subprocess.run(["node", str(Path(__file__).with_name("capture_provenance_screenshots.mjs")), str(out)], cwd=ROOT, check=True)
    capture = json.loads((out / "browser.json").read_text())
    sources = capture["sources"]
    ground_truth = []
    features = {}

    def pair(split, left, right, expected, category, left_area=None, right_area=None):
        ground_truth.append(dict(split=split, left=left, right=right, expected_link=expected,
                                 category=category, left_area=left_area, right_area=right_area))

    for split in ("development", "test"):
        group = [item for item in sources if item["split"] == split]
        for item in group:
            for variant, suffix in (("crop","png"), ("compressed","jpg")):
                pair(split,item["original"],f"{item['family']}-{variant}.{suffix}",True,variant)
            pair(split,item["original"],item["screenshot"],True,"screenshot",right_area=item["area"])
            pair(split,item["original"],f"{item['family']}-independent-render.png",False,"same-layout independent render")
        for left,right in itertools.combinations(group,2):
            pair(split,left["screenshot"],right["screenshot"],False,"shared browser frame",left["area"],right["area"])
            pair(split,left["original"],right["original"],False,"different source, similar scene layout")

    # Separate challenge. The existing generated derivative was prompted from the base.
    # Its generation history establishes the expected relation, even if geometry has changed.
    for source,name in (("A-synthetic-base.png","ai-base.png"),("C-cropped-view.png","ai-regenerated-crop.png")):
        asset = ROOT / "testing" / "provenance" / source
        if not asset.is_file():
            asset = asset.parent / "synthetic-demo" / source
        shutil.copyfile(asset, out / name)
    pair("challenge","ai-base.png","ai-regenerated-crop.png",True,"AI-regenerated derivative")

    def visual(name, area):
        key = (name,tuple(area or ()))
        if key not in features:
            with Image.open(out / name) as asset:
                image=ImageOps.exif_transpose(asset).convert("RGB")
            image.thumbnail((1200,1200))
            features[key]=prepare_visual(image,area)
        return features[key]

    def run(rows, selected):
        supports=[]
        for row in rows:
            cv2.setRNGSeed(42)
            supports.append(compare_visual(
                visual(row["left"], row["left_area"] if selected else None),
                visual(row["right"], row["right_area"] if selected else None),
            ))
        return supports

    def links(supports, ratio):
        return [match is not None and match["geometric_inlier_ratio"] >= ratio for match in supports]

    def score(rows, predictions):
        true_total=sum(row["expected_link"] for row in rows)
        true_count=sum(result and row["expected_link"] for row,result in zip(rows,predictions))
        false_count=sum(result and not row["expected_link"] for row,result in zip(rows,predictions))
        false_total=len(rows)-true_total
        return dict(true_links=true_count,true_pairs=true_total,false_links=false_count,false_pairs=false_total,
                    true_rate_wilson95=wilson(true_count,true_total),false_rate_wilson95=wilson(false_count,false_total))

    dev=[row for row in ground_truth if row["split"]=="development"]
    dev_selected=run(dev,True)
    tuning=[{"ratio":ratio,**score(dev,links(dev_selected,ratio))} for ratio in (.45,.55,.65,.75)]
    frozen=min(tuning,key=lambda row:(row["false_links"],-row["true_links"],row["ratio"]))["ratio"]
    save_json(out / "frozen-policy.json", {
        "selected_min_inlier_ratio":frozen,"development_counts":tuning,
        "spatial_gate":"Inlier span >=12% of width and height of both compared areas, hull >=1.5% in both and >=5% in one",
        "min_inliers":16,"ransac_reprojection_pixels":4,
    })
    results={}
    for split in ("test","challenge"):
        rows=[row for row in ground_truth if row["split"]==split]
        whole=links(run(rows,False),.45)
        selected=links(run(rows,True),frozen)
        results[split]={"whole":score(rows,whole),"selected":score(rows,selected),
                        "pairs":[{**row,"whole_link":a,"selected_link":b} for row,a,b in zip(rows,whole,selected)]}
    save_json(out / "ground-truth.json",ground_truth)
    save_json(out / "results.json",results)
    save_json(out / "asset-sha256.json",{
        p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())
        if p.suffix in (".png",".jpg")
    })
    print(json.dumps({k:{name:value for name,value in result.items() if name!="pairs"} for k,result in results.items()},indent=2))


if __name__=="__main__":
    main()
