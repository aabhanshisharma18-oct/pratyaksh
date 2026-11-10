"""Execution check only; the generated solid colour has no authenticity label."""
import json

from PIL import Image

from detector import ImageDetector


if __name__ == "__main__":
    output = ImageDetector().predict(Image.new("RGB", (256, 256), "#808080"))
    print(
        json.dumps(
            {
                "purpose": "Execution smoke test only; not accuracy evaluation",
                "output": output,
            },
            indent=2,
        )
    )
