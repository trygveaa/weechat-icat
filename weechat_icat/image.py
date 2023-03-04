from __future__ import annotations

import io

from PIL import Image


def load_image_data(path: str):
    with io.BytesIO() as data:
        with Image.open(path) as im:
            im.save(data, "png")
            return data.getvalue()
