"""Local comparison of Pratyaksh's visual matcher and pretrained LightGlue.

Run from the repo root with the backend venv. Pass a checkout of official
LightGlue, its SIFT checkpoint, and at least two independently sourced images.
The run processes images locally and emits pair-level metrics, without images.
"""
import argparse
import hashlib
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provenance import compare_visual, prepare_visual, verify_visual_matches

CHECKPOINT_SHA256 = "5b52b8d9982d43532dc042606b346bb9594c9f5a4bd6f64362c63866287b4ac0"


def variants(image):
    width, height = image.size
    crop = image.crop((width // 3, height // 4, width * 2 // 3, height * 3 // 4))
    with io.BytesIO() as buffer:
        image.save(buffer, format="JPEG", quality=12)
        buffer.seek(0)
        compressed = Image.open(buffer).convert("RGB")
    screenshot = Image.new("RGB", (800, 650), "#e6eaf2")
    inset = ImageOps.contain(image, (510, 450))
    screenshot.paste(inset, (120, 94))
    chrome = ImageDraw.Draw(screenshot)
    chrome.rectangle((0, 0, 799, 66), fill="#26394d")
    chrome.rounded_rectangle((95, 15, 710, 49), radius=8, fill="#f4f6fb")
    chrome.text((112, 26), "Evidence viewer / image preview", fill="#1c2b39")
    for x in (19, 39, 59):
        chrome.ellipse((x, 26, x + 9, 35), fill="#8da9bd")
    chrome.text((120, 582), "Preview   |   Fit image   |   Zoom   |   File details", fill="#26394d")
    small = ImageOps.contain(crop, (150, 150))
    with io.BytesIO() as buffer:
        small.save(buffer, format="JPEG", quality=18)
        buffer.seek(0)
        small = Image.open(buffer).convert("RGB")
    return {"original": image, "crop": crop, "jpeg": compressed,
            "screenshot_simulation": screenshot, "small_compressed_crop": small}


def neural_features(visual, rootsift):
    points = visual["keypoints"]
    if not points:
        return None
    height, width = visual["gray"].shape
    return {
        "keypoints": torch.tensor([[k.pt for k in points]]),
        "scales": torch.tensor([[k.size for k in points]]),
        "oris": torch.tensor(np.deg2rad([[k.angle for k in points]]), dtype=torch.float32),
        "descriptors": rootsift(torch.from_numpy(visual["descriptors"])[None]),
        "image_size": torch.tensor([[width, height]], dtype=torch.float32),
    }


def measure(call):
    cv2.setRNGSeed(42)
    start = perf_counter()
    result = call()
    return {
        "linked": result is not None,
        "inliers": result["matched_features"] if result else None,
        "milliseconds": round((perf_counter() - start) * 1000, 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lightglue", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("images", nargs="+", type=Path)
    args = parser.parse_args()
    if len(args.images) < 2:
        parser.error("Provide at least two independently sourced images")
    if hashlib.sha256(args.weights.read_bytes()).hexdigest() != CHECKPOINT_SHA256:
        parser.error("SIFT checkpoint SHA-256 mismatch")
    sys.path.insert(0, str(args.lightglue.resolve()))
    from lightglue import LightGlue
    from lightglue.sift import sift_to_rootsift

    torch.set_num_threads(4)
    weights = torch.load(args.weights, map_location="cpu", weights_only=True)
    with patch.object(torch.hub, "load_state_dict_from_url", return_value=weights):
        model = LightGlue(features="sift", flash=False).eval()

    def prepare(image):
        image.thumbnail((1200, 1200))
        visual = prepare_visual(image)
        return visual, neural_features(visual, sift_to_rootsift)

    families = []
    for path in args.images:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1200, 1200))
        families.append({name: prepare(variant) for name, variant in variants(image).items()})

    @torch.inference_mode()
    def neural_match(left, right):
        if left[1] is None or right[1] is None:
            return None
        matches = model({"image0": left[1], "image1": right[1]})["matches"][0]
        return verify_visual_matches(left[0], right[0], matches.tolist(), "SIFT + LightGlue + RANSAC")

    neural_match(families[0]["original"], families[0]["crop"])
    rows = []

    def compare(left_id, right_id, kind, expected, left_kind="original"):
        left = families[left_id][left_kind]
        right = families[right_id][kind]
        rows.append({
            "left": left_id + 1, "right": right_id + 1, "left_variant": left_kind, "right_variant": kind,
            "expected_link": expected,
            "sift": measure(lambda: compare_visual(left[0], right[0])),
            "lightglue": measure(lambda: neural_match(left, right)),
        })

    for index, family in enumerate(families):
        for kind in family:
            if kind != "original":
                compare(index, index, kind, True)
    for left, right in itertools.combinations(range(len(families)), 2):
        for kind in ("original", "small_compressed_crop"):
            compare(left, right, kind, False)
        compare(left, right, "screenshot_simulation", False, "screenshot_simulation")
    output = {
        "source_count": len(families),
        "lightglue_revision": subprocess.check_output(
            ["git", "-C", str(args.lightglue), "rev-parse", "HEAD"], text=True
        ).strip(),
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "opencv": cv2.__version__, "torch": torch.__version__,
        "lightglue_configuration": vars(model.conf),
        "pairs": rows,
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
