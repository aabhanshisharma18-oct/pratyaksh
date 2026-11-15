"""Compare SBI scores for spatially matched faces after controlled image edits."""
import base64
import io

from PIL import Image


def jpeg(image, quality):
    stream = io.BytesIO()
    image.save(stream, format="JPEG", quality=quality)
    return stream.getvalue()


def normalized_box(face, size):
    return [value / size[index % 2] for index, value in enumerate(face["bbox_xyxy"])]


def overlap(a, b):
    width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = width * height
    union = (a[2]-a[0]) * (a[3]-a[1]) + (b[2]-b[0]) * (b[3]-b[1]) - intersection
    return intersection / union if union > 0 else 0


def compare_face_scores(image, detector, supplied_copy=None):
    original = detector.predict(image)
    originals = original["faces"]
    reference = [normalized_box(face, image.size) for face in originals]
    variants = []
    if originals:
        if supplied_copy is not None:
            variants.append(("Uploaded comparison image", supplied_copy))
        else:
            resized = image.resize(tuple(max(1, round(length * 0.5)) for length in image.size),
                                   Image.Resampling.LANCZOS)
            with Image.open(io.BytesIO(jpeg(image, 35))) as decoded:
                compressed = decoded.convert("RGB")
            variants = [("Compressed JPEG (quality 35)", compressed), ("Resized copy (50%)", resized)]

    def record(label, variant, matches):
        thumbnail = variant.copy()
        thumbnail.thumbnail((480, 480), Image.Resampling.LANCZOS)
        return {
            "label": label, "width": variant.width, "height": variant.height,
            "thumbnail": base64.b64encode(jpeg(thumbnail, 85)).decode("ascii"),
            "faces": [
                {"box": normalized_box(face, variant.size), "score": face["face_forgery_score"]}
                if face is not None else None for face in matches
            ],
        }

    versions = [record("Uploaded photo", image, originals)]
    for label, variant in variants:
        faces = detector.predict(variant)["faces"] if min(variant.size) >= 32 else []
        boxes = [normalized_box(face, variant.size) for face in faces]
        candidates = [[index for index, box in enumerate(boxes) if overlap(ref, box) >= 0.5]
                      for ref in reference]
        matches = [
            faces[indices[0]] if len(indices) == 1 and
            sum(indices[0] in other for other in candidates) == 1 else None
            for indices in candidates
        ]
        versions.append(record(label, variant, matches))
    return {"model_id": detector.model_id, "model_version": detector.model_version,
            "checkpoint_sha256": original.get("checkpoint_sha256"),
            "versions": versions}
